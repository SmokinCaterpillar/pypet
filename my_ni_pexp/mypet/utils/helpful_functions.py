__author__ = 'robert'



def flatten_dictionary(nested_dict, separator):
    flat_dict = {}
    for key, val in nested_dict.items():
        if isinstance(val,dict):
            new_flat_dict = flatten_dictionary(val, separator)
            for flat_key, val in new_flat_dict.items():
                new_key = key + separator + flat_key
                flat_dict[new_key] = val
        else:
            flat_dict[key] = val

    return flat_dict

def nest_dictionary(flat_dict, separator):
    nested_dict = {}
    for key, val in flat_dict.items():
        split_key = key.split(separator)
        act_dict = nested_dict
        final_key = split_key.pop()
        for new_key in split_key:
            if not new_key in act_dict:
                act_dict[new_key] ={}

            act_dict = act_dict[new_key]

        act_dict[final_key] = val
    return nested_dict


