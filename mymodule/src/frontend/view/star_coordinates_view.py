"""
    STAR COORDINATES VIEW
"""

from __future__ import division
import logging
from bokeh.layouts import row, column
from bokeh.plotting import figure
from bokeh.models import Label, ColumnDataSource, LabelSet, HoverTool, WheelZoomTool,\
                         PanTool, PolySelectTool, TapTool, ResizeTool, SaveTool, ResetTool

from ...backend.io.reader import Reader

from .controllers.input_data_controller import InputDataController
from .controllers.vector_controller import VectorController
from .controllers.mapper_controller import MapperController
from .controllers.normalization_controller import NormalizationController
from .controllers.classification_controller import ClassificationController
from .controllers.cluster_controller import ClusterController
from .controllers.file_controller import FileController
from .controllers.point_size_controller import PointSizeController
from .controllers.point_controller import PointController
from .controllers.error_controller import ErrorController
from .controllers.color_controller import ColorController
from .controllers.hover_controller import HoverController
from .figure_element.axis_figure_element import AxisFigureElement
from ..bokeh_extension.dragtool import DragTool
from .animation.mapping_animator import MappingAnimator


class StarCoordinatesView(object):
    """A Star Coordinates oriented view with all the necessary logic
       to interact with it and displaying it on bokeh
    """
    LOGGER = logging.getLogger(__name__)
    _SEGMENT_COLOR = "#F4A582"
    _SEGMENT_WIDTH = 2

    _SQUARE_SIZE = 7
    _SQUARE_COLOR = "#74ADD1"
    _SQUARE_ALPHA = 0.5

    _CIRCLE_ALPHA = 0.5

    _POINT_LABEL_SIZE = '7pt'

    _N_A = 'N/A'

    POINT_LABEL_OPTIONS = ['ON', 'OFF']

    # The center is a constant across the application and should not be modified
    CENTER_POINT = (0, 0)

    @staticmethod
    def _set_source_attribute(source, attr_name, attr_list):
        source.add(attr_list, name=attr_name)

    def __init__(self, alias, filename=None, width=800, height=800):
        """Creates a new Star Coordinates View object and instantiates
           its elements
        """
        self._alias = alias
        # Configuration elements
        self._width = width
        self._height = height
        self._filename = filename
        self._reader = None
        self._selected_axis = None
        # Figure elements
        self._figure = None
        self._layout = None
        self._drag_tool_sources = None
        self._axis_sources = []
        self._axis_elements = dict()
        self._square_mapper = None
        self._source_points = None
        self._mapped_points = None
        self._labels_points = None
        self._checkboxes = None
        self._table_widget = None
        # Controllers
        self._input_data_controller = None
        self._vector_controller = None
        self._mapper_controller = None
        self._normalization_controller = None
        self._cluster_controller = None
        self._file_controller = None
        self._axis_checkboxes = None
        self._point_controller = None
        self._point_size_controller = None
        self._error_controller = None
        self._color_controller = None
        self._hover_controller = None
        # Logic to initialize all the elements from above
        self._init()

    # Private methods
    def _init(self):
        """Load data from file and initialize dataframe values"""
        self._file_controller = FileController(filename=self._filename)

        raw_input_df = Reader.read_from_file(self._file_controller.get_active_file())
        self._input_data_controller = InputDataController(raw_input_df)
        self._vector_controller = VectorController(self._input_data_controller)
        self._normalization_controller = NormalizationController(self._input_data_controller)
        self._normalization_controller.execute_normalization()

        # Initialize figure and axis
        self._figure = self._init_figure()
        self._axis_sources = self._init_axis()

        # Add our custom drag and drop tool for resizing axis
        self._drag_tool_sources = ColumnDataSource(dict(active_sources=[]))
        self._drag_tool_sources.data['active_sources'] = [source for source in self._axis_sources]
        self._square_mapper = self._init_square_mapper()
        self._figure.add_tools(DragTool(sources=self._drag_tool_sources,
                                        remap_square=self._square_mapper))

        self._cluster_controller = ClusterController(self._normalization_controller)
        self._cluster_controller.execute_clustering()
        self._classification_controller = ClassificationController(self._input_data_controller,
                                                                   self._cluster_controller,
                                                                   self._normalization_controller,
                                                                   self._axis_sources)

        self._point_controller = PointController(self._input_data_controller,
                                                 self._classification_controller)

        mapping_animator = MappingAnimator(self._point_controller)
        self._mapper_controller = MapperController(self._input_data_controller,
                                                   self._point_controller,
                                                   self._vector_controller,
                                                   self._normalization_controller,
                                                   animator=mapping_animator)
        self._mapper_controller.execute_mapping()

        # We assign to the mapper controller the animator
        self._error_controller = ErrorController(self._normalization_controller,
                                                 self._vector_controller,
                                                 self._mapper_controller,
                                                 self._point_controller,
                                                 self._axis_sources)
        self._error_controller.calculate_error()

        self._point_size_controller = PointSizeController(self._error_controller,
                                                          self._point_controller)
        self._point_size_controller.update_sizes()
        self._color_controller = ColorController(self._input_data_controller,
                                                 self._normalization_controller,
                                                 self._classification_controller,
                                                 self._point_controller)
        self._color_controller.update_colors()

        # Add the nominal and dimensional columns to the source_points so we can show them in the hover
        self._set_values_to_sources(self._input_data_controller.get_dimensional_labels())
        self._set_values_to_sources(self._input_data_controller.get_nominal_labels())

        self._init_points()
        self._layout = column(self._figure)

    def _set_values_to_sources(self, labels):
        for label in labels:
            values = self._input_data_controller.get_column_from_raw_input(label)
            self._point_controller.add_attribute(label, values)
            # Additionally, set 'N/A' to the axis
            # TODO gchicafernandez - Remove once axis widget has been implemented
            for axis_source in self._axis_sources:
                axis_source.add([StarCoordinatesView._N_A for i in values], name=label)

    def _init_square_mapper(self):
        def remap(attr, old, new):
            StarCoordinatesView.LOGGER.debug("Remap - Drag && Drop")
            StarCoordinatesView.LOGGER.debug("axis: %s; x: %s; y: %s",
                                             self._square_mapper.glyph.name,
                                             self._square_mapper.glyph.x,
                                             self._square_mapper.glyph.y)
            modified_axis_id = self._square_mapper.glyph.name
            self._vector_controller.update_single_vector(modified_axis_id,
                                                         self._square_mapper.glyph.x,
                                                         self._square_mapper.glyph.y)
            # The axis position won't be persisted across views unless we
            # update the source's value on the python's side
            for source in self._axis_sources:
                if source.data['name'][0] == modified_axis_id:
                    source.data['x1'][0] = self._square_mapper.glyph.x
                    source.data['y1'][0] = self._square_mapper.glyph.y
            self._execute_mapping()

        square = self._figure.square(x=0, y=0, name='remap', size=0)
        square.on_change('visible', remap)
        return square

    def _init_figure(self):
        """Updates the visual elements on the figure"""
        wheel_zoom_tool = WheelZoomTool()
        pan_tool = PanTool()
        resize_tool = ResizeTool()
        save_tool = SaveTool()
        reset_tool = ResetTool()
        figure_ = figure(tools=[wheel_zoom_tool, pan_tool, resize_tool, save_tool, reset_tool],
                         width=self._width, height=self._height)
        figure_.toolbar.active_scroll = wheel_zoom_tool
        
        hover_tips = ['name'] \
                    + self._input_data_controller.get_nominal_labels() \
                    + self._input_data_controller.get_dimensional_labels()

        if self._hover_controller is None:
            self._hover_controller = HoverController(figure_, properties=hover_tips)
        else:
            self._hover_controller.set_new_figure(figure_)

        return figure_

    def _add_axis_element(self, source, name, is_visible):
        segment = self._figure.segment(x0='x0',
                                       y0='y0',
                                       x1='x1',
                                       y1='y1',
                                       name=name,
                                       color='color',
                                       line_width='line_width',
                                       source=source)

        square = self._figure.square(x='x1',
                                     y='y1',
                                     source=source,
                                     name=name,
                                     size=StarCoordinatesView._SQUARE_SIZE,
                                     color=StarCoordinatesView._SQUARE_COLOR,
                                     alpha=StarCoordinatesView._SQUARE_ALPHA)

        axis_figure_element = AxisFigureElement(segment, square)
        axis_figure_element.visible(is_visible)
        self._axis_elements[axis_figure_element.get_identifier()] = axis_figure_element
        # Axis labels (name of their associated column)
        labels_dimensions = LabelSet(x='x1', y='y1', text='name', name='name', level='glyph',
                                     x_offset=5, y_offset=5, source=source,
                                     render_mode='canvas')
        self._figure.add_layout(labels_dimensions)

    def _init_axis(self, activation_list=None):
        """Will render all axis (Segment, Square and Label) creating
           for each one a source and an AxisFigureElement

           [activation_list=None]: list with axis indexes to be visible
                                   by default. If none is specified, all
                                   of them will be visible

           Returns: (ColumnDataSource[]) list of sources (where each
                        source is the base source of one axis)
                    (AxisFigureElement[]) list of generated axis elements
        """
        sources_list = []
        vectors_df = self._vector_controller.get_vectors()
        x0, y0 = StarCoordinatesView.CENTER_POINT
        # Segments and squares
        for i in range(0, len(vectors_df['x'])):
            x1 = vectors_df['x'][i]
            y1 = vectors_df['y'][i]
            error = 0
            name = vectors_df.index.values[i]
            source = ColumnDataSource(dict(x0=[x0],
                                           y0=[y0],
                                           x1=[x1],
                                           y1=[y1],
                                           name=[name],
                                           error=[error],
                                           color=[StarCoordinatesView._SEGMENT_COLOR],
                                           line_width=[StarCoordinatesView._SEGMENT_WIDTH]))
            is_visible = not activation_list or i in activation_list
            self._add_axis_element(source, name, is_visible)
            # Add source to the list of sources for the error calculation upon axis
            sources_list.append(source)

        return sources_list

    def _init_points(self):
        """Will draw the circles representing the dots on the plot
           source_points: (ColumnDataSource) x, y, size and color for each point
        """
        source_points = self._point_controller.get_source()
        self._figure.circle('x',
                            'y',
                            size='size',
                            color='color',
                            alpha=StarCoordinatesView._CIRCLE_ALPHA,
                            legend='category',
                            source=source_points)

        self._labels_points = LabelSet(x='x', y='y', text='name', name='name', level='glyph',
                                       x_offset=5, y_offset=5, text_font_size='0pt',
                                       source=source_points, render_mode='canvas')

        self._figure.add_layout(self._labels_points)

    def _execute_mapping(self):
        self._mapper_controller.execute_mapping()
        self._execute_error_recalc()

    def _execute_clustering(self):
        self._cluster_controller.execute_clustering()
        if self._classification_controller.in_clustering_mode():
            if self._color_controller.in_category_mode():
                self._color_controller.update_colors()
            self._execute_classification()

    def _execute_classification(self):
        self._color_controller.update_legend()
        if self._classification_controller.in_active_mode():
            vectors_df = self._classification_controller.relocate_axis()
            self._vector_controller.update_vector_values(vectors_df)
            self._execute_mapping()

    def _execute_error_recalc(self):
        self._error_controller.calculate_error()
        self._point_size_controller.update_sizes()

    def _execute_normalization(self):
        self._normalization_controller.execute_normalization()
        self._execute_mapping()

    def _update_layout(self):
        self._layout = row(self._figure, name='view')

    def _is_valid_point(self, name):
        return self._point_controller.is_valid_point(name)

    # PUBLIC methods available to the model
    def redraw(self):
        # Redraw plot
        self._figure = self._init_figure()
        # Add tools to new plot
        self._figure.add_tools(DragTool(sources=self._drag_tool_sources,
                                        remap_square=self._square_mapper))
        # Redraw axis elements
        for source in self._axis_sources:
            name = source.data['name'][0]
            is_visible = self._input_data_controller.is_label_active(name)
            self._add_axis_element(source, name, is_visible)
        # Redraw points
        self._init_points()

    # UPDATE methods
    def update_mapping_algorithm(self, new):
        self._mapper_controller.update_algorithm(new)
        self._execute_mapping()

    def update_classification_algorithm(self, new):
        self._classification_controller.update_algorithm(new)
        self._execute_classification()

    def update_normalization_algorithm(self, new):
        self._normalization_controller.update_algorithm(new)
        self._execute_normalization()

    def update_clustering_algorithm(self, new):
        self._cluster_controller.update_algorithm(new)
        self._execute_clustering()

    def update_error_algorithm(self, new):
        self._error_controller.update_algorithm(new)
        self._execute_error_recalc()

    def update_selected_axis(self, new):
        self._selected_axis = new
        self._color_controller.update_selected_axis(new)
        if self._color_controller.in_axis_mode():
            self._color_controller.update_colors()

    def update_selected_category_source(self, new):
        self._classification_controller.update_active_source(new)
        if self._color_controller.in_category_mode():
            self._color_controller.update_colors()
        self._execute_classification()

    def update_color_method(self, new):
        self._color_controller.update_method(new)
        self._color_controller.update_colors()

    def update_palette(self, new):
        self._color_controller.update_palette(new)
        if self._color_controller.in_axis_mode():
            self._color_controller.update_colors()

    def update_axis_visibility(self, new):
        axis_id, is_visible = new
        if not axis_id in self._axis_elements:
            ValueError("Could not update the visibility of the axis '{}'\
                        because it is not a valid axis".format(axis_id))
        self._input_data_controller.update_label_status(axis_id, is_visible)
        # Tries to hide the axis element. If a change is made then execute mapping
        if self._axis_elements[axis_id].visible(is_visible):
            self._execute_mapping()

    def update_hover_tips_visibility(self, new):
        hover_tip, is_visible = new
        if (not is_visible and self._hover_controller.is_active_property(hover_tip))\
            or (is_visible and not self._hover_controller.is_active_property(hover_tip)):
            self._hover_controller.toggle_property(hover_tip)

    def update_point_label_visibility(self, new):
        if new == 'ON':
            self._labels_points.text_font_size = StarCoordinatesView._POINT_LABEL_SIZE
        else:
            self._labels_points.text_font_size = '0pt'

    def update_number_of_clusters(self, new):
        # Will update the cluster categories too
        self._cluster_controller.update_number_of_clusters(new)
        self._execute_clustering()

    def update_initial_size_input(self, new):
        self._point_size_controller.set_initial_size(new)

    def update_final_size_input(self, new):
        self._point_size_controller.set_final_size(new)

    def update_selected_point(self, new):
        """Updates the color based on the point if valid
           if not, returns to previous color settings
        """
        if self._is_valid_point(new):
            self._color_controller.select_point(new)
        else:
            self._color_controller.unselect_point()

    # GET methods
    def get_alias(self):
        return self._alias

    def get_mapping_algorithm(self):
        return self._mapper_controller.get_active_algorithm_id()

    def get_mapping_options(self):
        return self._mapper_controller.get_all_options()

    def get_classification_algorithm(self):
        return self._classification_controller.get_active_algorithm_id()

    def get_classification_methods(self):
        return self._classification_controller.get_available_methods()

    def get_normalization_algorithm(self):
        return self._normalization_controller.get_active_algorithm_id()

    def get_normalization_options(self):
        return self._normalization_controller.get_all_options()

    def get_clustering_algorithm(self):
        return self._cluster_controller.get_active_algorithm_id()

    def get_clustering_options(self):
        return self._cluster_controller.get_all_options()

    def get_error_algorithm(self):
        return self._error_controller.get_active_algorithm_id()

    def get_error_options(self):
        return self._error_controller.get_all_options()

    def get_axis_status(self):
        """Returns a zipped list of [(axis_id, visible), ..]"""
        return self._input_data_controller.get_dimensional_labels_status()

    def get_number_of_clusters(self):
        return self._cluster_controller.get_number_of_clusters()

    def get_initial_size(self):
        return self._point_size_controller.get_initial_size()

    def get_final_size(self):
        return self._point_size_controller.get_final_size()

    def get_file(self):
        return self._file_controller.get_active_file()

    def get_available_files(self):
        return self._file_controller.get_available_files()

    def get_dimension_values_df(self):
        return self._input_data_controller.get_dimensional_values()

    def get_available_axis_ids(self):
        return self._color_controller.get_available_axis_ids()

    def get_axis_checkboxes_options(self):
        return self._input_data_controller.get_dimensional_labels()

    def get_checkboxes_active_axis_ids(self):
        return self._input_data_controller.get_dimensional_labels(filtered=True)

    def get_selected_axis_id(self):
        return self._color_controller.get_selected_axis_id()

    def get_hover_tips_active_ids(self):
        return self._hover_controller.get_active_properties()

    def get_hover_tips_options(self):
        return self._hover_controller.get_available_properties()

    def get_active_color_method(self):
        return self._color_controller.get_active_color_method()

    def get_available_color_methods(self):
        return self._color_controller.get_available_color_methods()

    def get_available_category_sources(self):
        return self._classification_controller.get_available_category_sources()

    def get_active_category_source(self):
        return self._classification_controller.get_active_source()

    def get_palette(self):
        return self._color_controller.get_active_palette()

    def get_available_palettes(self):
        return self._color_controller.get_available_palettes()

    def get_point_names(self):
        return self._point_controller.get_point_names()

    def get_selected_point(self):
        return self._color_controller.get_selected_point()

    def get_layout(self):
        self._update_layout()
        return self._layout

    def get_point_label_visibility(self):
        if self._labels_points.text_font_size == StarCoordinatesView._POINT_LABEL_SIZE:
            return 'ON'
        return 'OFF'

    def get_point_label_options(self):
        return StarCoordinatesView.POINT_LABEL_OPTIONS

    def set_checkboxes(self, checkboxes):
        self._checkboxes = checkboxes
        self._checkboxes.update_view(self)
        self._update_layout()
