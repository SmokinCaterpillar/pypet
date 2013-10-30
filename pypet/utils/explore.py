'''
Created on 24.05.2013
'''
import itertools as itools



def cartesian_product(parameter_dict, combined_parameters = ()):
    ''' Generates a Cartesian product of the input parameter dictionary.

    For example:

    >>> print cartesian_product({'param1':[1,2,3], 'param2':[42.0, 52.5]})
    {'param1':[1,1,2,2,3,3],'param2': [42.0,52.5,42.0,52.5,42.0,52.5]}

    :param param_dict:

        Dictionary containing parameter names as keys and iterables of data to explore.

    :param combined_parameter_list:

        Tuple of tuples. Defines the order of the parameters and parameters that are
        linked together.
        If an inner tuple contains only a single item, you can spare the
        inner tuple brackets.


        For example:

        >>> print cartesian_product( {'param1': [42.0, 52.5], 'param2':['a', 'b'],\
        'param3' : [1,2,3]}, ('param3',('param1', 'param2')))
        {param3':[1,1,2,2,3,3],'param1' : [42.0,52.5,42.0,52.5,42.0,52.5],\
        'param2':['a','b','a','b','a','b']}

    :returns: Dictionary with cartesian product lists.

    '''
    if not combined_parameters:
        combined_parameters = list(parameter_dict)
    else:
        combined_parameters = list(combined_parameters)

    for idx,item in enumerate(combined_parameters):
        if isinstance(item,basestring):
            combined_parameters[idx]= (item,)

    iterator_list = []
    for item_tuple in combined_parameters:
        inner_iterator_list = [parameter_dict[key] for key in item_tuple]
        zipped_iterator = itools.izip(*inner_iterator_list)
        iterator_list.append(zipped_iterator)

    result_dict ={}
    for key in parameter_dict:
        result_dict[key]=[]

    cartesian_iterator = itools.product(*iterator_list)

    for cartesian_tuple in cartesian_iterator:
        for idx, item_tuple in enumerate(combined_parameters):
            for inneridx,key in enumerate(item_tuple):
                result_dict[key].append(cartesian_tuple[idx][inneridx])

    return result_dict




# def cartesian_product_old(param_dict, combined_parameter_list=[]):
#     ''' Generates a Cartesian product of the input parameters.
#
#
#     For example:
#
#     >>> print cartesian_product({'param1.entry1':[1,2,3], 'param2.entry1' = [42.0, 42.5]})
#     {'param1.entry1':[1,1,2,2,3,3],'param2.entry2' = [42.0,42.5,42.0,42.5,42.0,42.5]}
#
#     :param param_dict:
#
#         Dictionary containing parameter names as keys and lists of data to explore
#
#     :param combined_parameter_list:
#
#         List of tuples. Defines the order of the parameters and parameters that are linked together.
#
#     :returns: Dictionary with cartesian product lists.
#
#     '''
#     if not combined_parameter_list:
#         combined_parameter_list = list(param_dict)
#
#     for key in param_dict:
#         inlist = False
#         for ptuple in combined_parameter_list:
#             if isinstance(ptuple,basestring):
#                 ptuple=(ptuple,)
#
#             if key in ptuple:
#                 inlist = True
#                 break
#
#         if not inlist:
#             combined_parameter_list.append((key,))
#
#
#     idx_lists = []
#     for idx, paramtuple in enumerate(combined_parameter_list):
#         if not isinstance(paramtuple, tuple):
#             combined_parameter_list[idx] = (combined_parameter_list[idx],)
#             paramtuple = combined_parameter_list[idx]
#
#         for idx, param in enumerate(paramtuple):
#             value_list = param_dict[param]
#             # if not isinstance(value_list, list):
#             #     raise TypeError(param + ' is not a list, why should I _explore it anyway?')
#
#             if idx == 0:
#                 param_length = len(value_list)
#                 idx_lists.append(range(param_length))
#             else:
#                 if not param_length == len(value_list):
#                     raise TypeError('Lists of two combined parameters are unequal!')
#
#
#     product_lists = list(itools.product(*idx_lists))
#     zipped_lists = zip(*product_lists)
#
#     result_dict={}
#     result_combined_list=[[]]
#     for idx, ituple in enumerate(zipped_lists):
#         for param in combined_parameter_list[idx]:
#             result_dict[param] = []
#             result_combined_list[0].append(param)
#             for tupidx in ituple:
#                 result_dict[param].append(param_dict[param][tupidx])
#
#     # result_combined_list[0]=tuple(result_combined_list[0])
#     return result_dict
            
                
        
