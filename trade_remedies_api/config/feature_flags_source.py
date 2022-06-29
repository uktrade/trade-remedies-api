from flags import conditions

from config.feature_flags import part_of_group_condition




class CustomFlagSource(object):

    def get_flags(self):
        flags = {
            'ROI_USERS': [
                conditions.get_condition("PART_OF_GROUP")
            ],
        }
        return flags
