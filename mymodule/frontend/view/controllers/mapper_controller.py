"""
    Mapper Controller Module
"""
import logging
from ....backend.algorithms.mapping.mapping_register import MappingRegister
from ....backend.algorithms.mapping.dummy_coordinates_mapper import DUMMY_COORDINATES_ID
from .abstract_algorithm_controller import AbstractAlgorithmController

class MapperController(AbstractAlgorithmController):
    """Controller that handles mapping operations
       It keeps the original dimension values and vectors and enables options
       to perform remapping by modifying particular vectors (e.g hiding an axis)
    """
    LOGGER = logging.getLogger(__name__)

    def __init__(self, input_data_controller, vector_controller, normalization_controller,
                 source_points=None, mapping_id=None, animator=None):
        algorithm_dict = MappingRegister.get_algorithm_dict()
        super(MapperController, self).__init__(DUMMY_COORDINATES_ID,
                                               algorithm_dict,
                                               active_algorithm_id=mapping_id,
                                               none_algorithm=False)
        self._input_data_controller = input_data_controller
        self._vector_controller = vector_controller
        self._normalization_controller = normalization_controller
        self._source_points = source_points
        self._animator = animator
        self._last_mapped_points_df = None
        #self._ignored_axis_ids = set()

    #def update_axis_status(self, axis_id, visible):
    #    """Adds an ID to the list of ignored axis if not visible, remove from it
    #       otherwise
    #       axis_id: (String) ID (name) of the axis as appears in the Dataframes
    #       visible: (Boolean) self explanatory
    #    """
    #    if visible:
    #        MapperController.LOGGER.debug("Updating axis '%s' to visible", axis_id)
    #        self._ignored_axis_ids.discard(axis_id)
    #    else:
    #        MapperController.LOGGER.debug("Updating axis '%s' to NOT visible", axis_id)
    #        self._ignored_axis_ids.add(axis_id)

    #def is_axis_visible(self, axis_id):
    #    return not axis_id in self._ignored_axis_ids

    #def get_axis_status(self):
    #    """Returns: list of tuples (axis_id, visible) generated from the
    #       correlation between the vectors dataframe' index and the
    #       ignored_axis_ids set
    #    """
    #    return [(axis_id, self.is_axis_visible(axis_id)) \
    #            for axis_id in self._vectors_df.index.tolist()]

    def execute_mapping(self):
        """Will recalculate the mapping for the points
           Returns: (pandas.DataFrame) Mapped points with shape
                    (point_name X {x, y})
        """
        # Note: this values are filtered according to the ignored labels set of
        # InputDataController
        dimension_values_df_norm = self._normalization_controller.get_last_normalized_values()
        vectors_df = self._vector_controller.get_vectors()
        MapperController.LOGGER.debug("Mapping with %s", self.get_active_algorithm_id())
        mapped_points_df = self.execute_active_algorithm(dimension_values_df_norm,
                                                         vectors_df)
        if self._animator:
            MapperController.LOGGER.debug("Executing animation")
            self._animator.get_animation_sequence(self._last_mapped_points_df,
                                                  mapped_points_df)        
        self._last_mapped_points_df = mapped_points_df
        if self._source_points:
            self._update_source_points(mapped_points_df)

        return mapped_points_df

    def get_mapped_points(self):
        return self._last_mapped_points_df

    def set_animator(self, animator):
        """ animator: (MappingAnimator) animator in charge of reproducing the
            transition from the original points to the mapped ones
        """
        MapperController.LOGGER.debug("Updating animator")
        self._animator = animator

    def set_source_points(self, source_points):
        self._source_points = source_points

    def _update_source_points(self, mapped_points_df):
        self._source_points.data['x'] = mapped_points_df['x']
        self._source_points.data['y'] = mapped_points_df['y']

    #def update_dimension_values(self, dimension_values_df):
    #    MapperController.LOGGER.debug("Updating dimension values")
    #    self._dimension_values_df = dimension_values_df

    #def update_vector_values(self, vectors_df):
    #    MapperController.LOGGER.debug("Updating vector values")
    #    for vector_id in vectors_df.index:
    #        self._vectors_df['x'][vector_id] = vectors_df['x'][vector_id]
    #        self._vectors_df['y'][vector_id] = vectors_df['y'][vector_id]
    #
    #def update_single_vector(self, axis_id, x1, y1):
    #    """Updates the vectors dataframe with the new coordinates
    #       Typically used when an axis is resized
    #       axis_id: (String) self explanatory
    #       x1: (int) self explanatory
    #       y1: (int) self explanatory
    #    """
    #    # We assume that all axis start from the point (0,0)
    #    # Hence, all vectors are (x1 - 0), (y1 - 0)
    #    MapperController.LOGGER.debug("Updating vector '%s'", axis_id)
    #    self._vectors_df.loc[axis_id:axis_id, 'x'] = x1
    #    self._vectors_df.loc[axis_id:axis_id, 'y'] = y1
