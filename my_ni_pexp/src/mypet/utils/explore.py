'''
Created on 24.05.2013

@author: robert
'''
import itertools as itools


def identity(param_value_list_dict):
    return param_value_list_dict


def cartesian_product(param_value_list_dict, combined_parameter_list=[]):
    
    if not combined_parameter_list:
        combined_parameter_list = list(param_value_list_dict)
    
    for key in param_value_list_dict:
        inlist = False
        for ptuple in combined_parameter_list:
            if key in ptuple:
                inlist = True
                break;
        
        if not inlist:
            combined_parameter_list.append((key,))
                    
    
    idx_lists = []
    for idx, paramtuple in enumerate(combined_parameter_list):
        if not isinstance(paramtuple, tuple):
            combined_parameter_list[idx] = (combined_parameter_list[idx],)
            paramtuple = combined_parameter_list[idx]
            
        for idx, param in enumerate(paramtuple):
            value_list = param_value_list_dict[param]
            if not isinstance(value_list, list):
                raise TypeError(param + ' is not a list, why should I explore it anyway?')
            
            if idx == 0:
                param_length = len(value_list)
                idx_lists.append(range(param_length))
            else:
                if not param_length == len(value_list):
                    raise TypeError('Lists of two combined parameters are unequal!')

    
    product_lists = list(itools.product(*idx_lists))
    zipped_lists = zip(*product_lists)
    
    result_dict={}
    result_combined_list=[[]]
    for idx, ituple in enumerate(zipped_lists):
        for param in combined_parameter_list[idx]:
            result_dict[param] = []
            result_combined_list[0].append(param)
            for tupidx in ituple:
                result_dict[param].append(param_value_list_dict[param][tupidx])
    
    result_combined_list[0]=tuple(result_combined_list[0])
    return result_dict, result_combined_list
            
                
        
        
    

# def _do_cartesian_product( value_lists):
# 
#     assert isinstance(value_lists, list)
#     
#     tuple_list =  list(itools.product(*value_lists))
#     
#     
#     zipped_list = zip(*tuple_list)
#     
#     result_lists = []
#     for ptuple in zipped_list:
#         result_lists.append(list(ptuple))
#     
#     return result_lists

# def _to_dictionary(param_name_list, value_lists):
#     
#     result_dict={}
#     for idx, param in enumerate(param_name_list):
#     
#         name_data = param.split(".")
#         param_name = ".".join(name_data[:-1])
#         value_str = name_data[-1]
#         
#         if not param_name in result_dict:
#             result_dict[param_name] = {}
#         
#         result_dict[param_name][value_str]= value_lists[idx]
#     
#     return result_dict