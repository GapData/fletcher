# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function

from pandas.compat.numpy import function as nv
from pandas.core.dtypes.dtypes import ExtensionDtype

import numpy as np
import pandas as pd
import pyarrow as pa

from ._numba_compat import NumbaStringArray, NumbaString
from ._algorithms import _startswith, _endswith, argsort_string_array
from .base import FletcherArrayBase


class StringDtypeType(object):
    """
    The type of StringDtype, this metaclass determines subclass ability
    """
    pass


class StringDtype(ExtensionDtype):
    name = "string"
    type = StringDtypeType
    kind = "O"

    @classmethod
    def construct_from_string(cls, string):
        if string == "string":
            return cls()
        else:
            raise TypeError("Cannot construct a '{}' from " "'{}'".format(cls, string))


class StringArray(FletcherArrayBase):
    dtype = StringDtype()

    def __init__(self, array):
        if isinstance(array, list):
            self.data = pa.chunked_array([pa.array(array, pa.string())])
        elif isinstance(array, pa.StringArray):
            self.data = pa.chunked_array([array])
        elif isinstance(array, pa.ChunkedArray):
            self.data = array
        else:
            raise ValueError(
                "Unsupported type passed for StringArray: {}".format(type(array))
            )

    def argsort(self, ascending=True, kind="quicksort", *args, **kwargs):
        """
        Return the indices that would sort this array.

        Parameters
        ----------
        ascending : bool, default True
            Whether the indices should result in an ascending
            or descending sort.
        kind : {'quicksort', 'mergesort', 'heapsort'}, optional
            Sorting algorithm.
        *args, **kwargs:
            passed through to :func:`numpy.argsort`.

        Returns
        -------
        index_array : ndarray
            Array of indices that sort ``self``.

        See Also
        --------
        numpy.argsort : Sorting implementation used internally.
        """
        ascending = nv.validate_argsort_with_ascending(ascending, args, kwargs)
        if kind != "quicksort":
            raise NotImplementedError("only kind=quicksort is implemented")

        result = argsort_string_array(self.data)

        if not ascending:
            result = result[::-1]
        return result


@pd.api.extensions.register_series_accessor("text")
class TextAccessor:

    def __init__(self, obj):
        if not isinstance(obj.values, StringArray):
            raise AttributeError("only StringArray has text accessor")
        self.obj = obj
        self.data = self.obj.values.data

    def startswith(self, needle, na=None):
        return self._call_x_with(_startswith, needle, na)

    def endswith(self, needle, na=None):
        return self._call_x_with(_endswith, needle, na)

    def _call_x_with(self, impl, needle, na=None):
        needle = NumbaString.make(needle)

        if isinstance(na, bool):
            result = np.zeros(len(self.data), dtype=np.bool)
            na_arg = np.bool_(na)

        else:
            result = np.zeros(len(self.data), dtype=np.uint8)
            na_arg = 2

        offset = 0
        for chunk in self.data.chunks:
            impl(NumbaStringArray.make(chunk), needle, na_arg, offset, result)
            offset += len(chunk)

        result = pd.Series(result, index=self.obj.index, name=self.obj.name)
        return (
            result if isinstance(na, bool) else result.map({0: False, 1: True, 2: na})
        )
