"""
    Reader Module
"""

from __future__ import division
import logging
from .file_reader import FileReader

class Reader(object):
    """Provides methods to get an input DataFrame out of a given source"""
    LOGGER = logging.getLogger(__name__)

    @staticmethod
    def read_from_file(file_path, header=True):
        """file_path: (String) path to source file to be read
           [header]: (Boolean) if the first line of the file is a header
           Returns: (pandas.DataFrame) input DataFrame
        """
        raw_input_df = FileReader.read_file(file_path, header=header)
        return raw_input_df

    # Methods to read from different sources can be added to this class
