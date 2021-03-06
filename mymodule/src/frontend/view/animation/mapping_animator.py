"""
    Mapping Animator
"""

from __future__ import division
import logging
import time
import pandas as pd
from ....backend.util.line_equation import calculate_line_equation


class MappingAnimator(object):
    """Object that creates animations between two positions for points"""
    LOGGER = logging.getLogger(__name__)

    def __init__(self, point_controller):
        """source_points: (ColumnDataSource) source where to update the values
        """
        self._point_controller = point_controller

    @staticmethod
    def step_x_exponential(step_points_df, final_points, step, total_steps):
        for i in range(0, len(step_points_df['x'])):
            x0 = step_points_df['x'][i]
            xf = final_points['x'][i]
            step_points_df['x'][i] = x0 + step * (xf - x0) / total_steps
        return step_points_df

    @staticmethod
    def step_x_constant(original_points, step_points_df, final_points, step, total_steps):
        for i in range(0, len(original_points['x'])):
            x0 = original_points['x'][i]
            xf = final_points['x'][i]
            step_points_df['x'][i] = x0 + step * (xf - x0) / total_steps
        return step_points_df

    @staticmethod
    def evaluate_y(points_df, formula):
        points_df.eval('y = {}'.format(formula), inplace=True)

    def calculate_time_cost(self, points_df, mapped_points, formula):
        start_time = time.time()
        MappingAnimator.step_x_exponential(points_df, mapped_points, 0, 1)
        MappingAnimator.evaluate_y(points_df, formula)
        self._point_controller.update_coordinates(points_df['x'], points_df['y'])
        end_time = time.time()
        time_cost = end_time - start_time
        MappingAnimator.LOGGER.debug("Time cost: {}s".format(time_cost))
        MappingAnimator.LOGGER.debug("Freq: {}s".format(1/time_cost))
        return time_cost

    def get_animation_sequence(self, original_points, mapped_points, max_time=2):
        """Will map the points for every step of the sequence by updating
           the ColumnDataSource

           original_points: (pandas.Dataframe) position of the points before
           mapped_points: (pandas.Dataframe) end position of the points
        """

        # First, we get the cost time by simulating an animation from P0 to P'0
        # where P'0 has the same coordinates (this way we include the
        # rendering time without modifying the position)
        # TODO gchicafernandez - Find a way to parallelize this. Takes forever!
        step_points_cp, formula = self._get_equation_dataframe(original_points, mapped_points)
        time_cost = self.calculate_time_cost(step_points_cp, mapped_points, formula)
        total_steps = int(max_time // time_cost)
        MappingAnimator.LOGGER.debug("Total steps: {}".format(total_steps))
        for step in range(0, total_steps):
            MappingAnimator.step_x_exponential(step_points_cp, mapped_points, step, total_steps)
            MappingAnimator.evaluate_y(step_points_cp, formula)
            self._point_controller.update_coordinates(step_points_cp['x'], step_points_cp['y'])

        MappingAnimator.LOGGER.debug("Finished animation")
        self._point_controller.update_coordinates(mapped_points['x'], mapped_points['y'])

    def _get_equation_dataframe(self, original_points, mapped_points):
        """Being the equation of the line: y = mx + c where m and c are
           constants, this method will return a dataframe composed by the
           following columns:
           'x': x points (with values as per original_points df)
           'm': calculated p constant for each point
           'c': calculated c constant for each point
           'y': equation 'mx + c'
        """
        formula = 'm * x + c'
        original_points_cp = original_points.copy()
        x_coords = zip(original_points['x'], mapped_points['x'])
        y_coords = zip(original_points['y'], mapped_points['y'])
        points = zip(x_coords, y_coords)
        m_l = []
        c_l = []
        for x0x1, y0y1 in points:
            m, c = calculate_line_equation(x0x1, y0y1)
            m_l.append(m)
            c_l.append(c)
        original_points_cp['m'] = pd.Series(m_l, index=original_points_cp.index)
        original_points_cp['c'] = pd.Series(c_l, index=original_points_cp.index)

        return original_points_cp, formula
