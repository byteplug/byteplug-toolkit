# Copyright (c) 2022 - Byteplug Inc.
#
# This source file is part of the Byteplug toolkit for the Python programming
# language which is released under the OSL-3.0 license. Please refer to the
# LICENSE file that can be found at the root of the project directory.
#
# Written by Jonathan De Wachter <jonathan.dewachter@byteplug.io>, June 2022

import re
import json
from byteplug.validator.utils import read_minimum_value, read_maximum_value
from byteplug.validator.exception import ValidationError

# Notes:
# - This module handles validation and conversion from JSON document to Python
#   object. It must be kept in sync with the 'object' module.
# - In all process_<type>_node(), it's about converting a JSON node (converted
#   to a Python object as defined by the 'json' module) and adjusting its value
#   based on the specs.
# - For each node type, we refer to the standard document that describes how
#   the augmented type is implemented in its JSON form; we care about validity
#   of its JSON form, its Python form is not defined by the standard.

__all__ = ['document_to_object']

def process_flag_node(path, node, specs, errors, warnings):
    if type(node) is not bool:
        error = ValidationError(path, "was expecting a JSON boolean")
        errors.append(error)
        return

    return node

def process_integer_node(path, node, specs, errors, warnings):

    # must be an number, converted to int or float
    # assert type(node) in (int, float)
    if type(node) not in (int, float):
        error = ValidationError(path, "was expecting a JSON number")
        errors.append(error)
        return

    minimum = read_minimum_value(specs)
    maximum = read_maximum_value(specs)

    if minimum:
        is_exclusive, value = minimum
        if is_exclusive:
            if not (node > value):
                error = ValidationError(path, "value must be strictly greater than X")
                errors.append(error)
                return
        else:
            if not (node >= value):
                error = ValidationError(path, "value must be equal or greater than X")
                errors.append(error)
                return

    if maximum:
        is_exclusive, value = maximum
        if is_exclusive:
            if not (node < value):
                error = ValidationError(path, "value must be strictly less than X")
                errors.append(error)
                return
        else:
            if not (node <= value):
                error = ValidationError(path, "value must be equal or less than X")
                errors.append(error)
                return

    # TODO; warning if losing precision
    return int(node)

def process_decimal_node(path, node, specs, errors, warnings):
    pass

def process_string_node(path, node, specs, errors, warnings):

    if type(node) is not str:
        raise ValidationError(path, "was expecting a JSON string")

    length = specs.get('length')
    if length is not None:
        if type(length) is int:
            if len(node) != length:
                error = ValidationError(path, "length of string must be equal to X")
                errors.append(error)
                return
        else:
            minimum = length.get("minimum")
            maximum = length.get("maximum")

            if minimum:
                if not (len(node) >= minimum):
                    error = ValidationError(path, "length of string must be greater or equal to X")
                    errors.append(error)
                    return

            if maximum:
                if not (len(node) <= maximum):
                    error = ValidationError(path, "length of string must be lower or equal to X")
                    errors.append(error)
                    return

    pattern = specs.get('pattern')
    if pattern is not None:
        if not re.match(pattern, node):
            raise ValidationError(path, "didnt match pattern")

    return node

def process_enum_node(path, node, specs, errors, warnings):
    if type(node) is not str:
        error = ValidationError(path, "was expecting a JSON string")
        errors.append(error)
        return

    values = specs['values']
    if node not in values:
        error = ValidationError(path, "value was expected to be one of [foo, bar, quz]")
        errors.append(error)
        return

    return node

def process_list_node(path, node, specs, errors, warnings):
    value = specs['value']

    if type(node) is not list:
        error = ValidationError(path, "was expecting a JSON array")
        errors.append(error)
        return

    length = specs.get('length')
    if length is not None:
        if type(length) is int:
            if len(node) != length:
                error = ValidationError(path, "length of list must be equal to X")
                errors.append(error)
                return
        else:
            minimum = length.get("minimum")
            maximum = length.get("maximum")

            if minimum:
                if not (len(node) >= minimum):
                    error = ValidationError(path, "length of list must be greater or equal to X")
                    errors.append(error)
                    return

            if maximum:
                if not (len(node) <= maximum):
                    error = ValidationError(path, "length of list must be lower or equal to X")
                    errors.append(error)
                    return

    # TODO; Rework this.
    adjusted_node = []
    for (index, item) in enumerate(node):
        adjusted_node.append(adjust_node(path + '.[' + str(index) + ']', item, value, errors, warnings))

    return adjusted_node

def process_tuple_node(path, node, specs, errors, warnings):
    values = specs['values']

    if type(node) is not list:
        error = ValidationError(path, "was expecting a JSON array")
        errors.append(error)
        return


    if len(node) != len(values):
        error = ValidationError(path, "was expecting array of N elements")
        errors.append(error)
        return

    # TODO; Rework this.
    adjusted_node = []
    for (index, item) in enumerate(node):
        adjusted_node.append(
            adjust_node(path + '.(' + str(index) + ')', item, values[index], errors, warnings)
        )

    return tuple(adjusted_node)


def process_map_node(path, node, specs, errors, warnings):
    fields = specs['fields']

    if type(node) is not dict:
        error = ValidationError(path, "was expecting a JSON object")
        errors.append(error)
        return

    # TODO; More things to do here.
    adjusted_node = {}
    for key, value in fields.items():
        if key in node:
            adjusted_node[key] = adjust_node(path + f'.{key}', node[key], value, errors, warnings)

    return adjusted_node

adjust_node_map = {
    'flag'   : process_flag_node,
    'integer': process_integer_node,
    'decimal': process_decimal_node,
    'string' : process_string_node,
    'enum'   : process_enum_node,
    'list'   : process_list_node,
    'tuple'  : process_tuple_node,
    'map'    : process_map_node
}

def adjust_node(path, node, specs, errors, warnings):
    optional = specs.get('option', False)
    if not optional and node is None:
        error = ValueError(path, "value cant be null")
        errors.append(error)
        return
    elif optional and node is None:
        return None
    else:
        return adjust_node_map[specs['type']](path, node, specs, errors, warnings)

def document_to_object(document, specs, errors=None, warnings=None):
    """ Convert a JSON document to its Python equivalent. """

    assert errors is None or errors == [], "if the errors parameter is set, it must be an empty list"
    assert warnings is None or warnings == [], "if the warnings parameter is set, it must be an empty list"

    # We detect if users want lazy validation when they pass an empty list as
    # the errors parameters.
    lazy_validation = False
    if errors is None:
        errors = []
    else:
        lazy_validation = True

    if warnings is None:
        warnings = []

    object = json.loads(document)
    adjusted_object = adjust_node("root", object, specs, errors, warnings)

    # If we're not lazy-validating the specs, we raise the first error that
    # occurred.
    if not lazy_validation and len(errors) > 0:
        raise errors[0]

    return adjusted_object
