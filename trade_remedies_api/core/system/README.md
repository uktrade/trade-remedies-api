# Trade Remedies - System Parameters

The parameters described in the `parameters.json` file are the runtime system params and 
switches of the system. They contain various controls to turn on/off certain features, 
or manipulate various flags in the app. 


Upon release those flags will only pick up NEW parameters to be set. Existing parameters 
will NOT be updated. This is the opposite of previous behaviour where each deployment refreshed the parameters to the values in the json file, often leading to undesired outcomes. 


The management command `./manage.py load_sysparams` will trigger the parsing and processing
of this json file. 



## load_sysparams 

`./manage.py load_sysparams`


Load system parameters. The file format is similiar to a standard fixture json with
the following differences:

1. `default` is used as initial value for the key if it does not exist in the database.
2. The absence of a `value` key for a specific parameter denotes retaining existing value.
3. The existence of a `value` key denotes updating to that value
4. Editable state of the parameter can be updated

Note: If a param contains the remove key as true, it will be removed from the
database if it exists, ignored otherwise. Removed keys can be kept or removed from the file in
future.

By default the file used is in `core/system/parameters.json`


Note that the **content** system parameters are still defined in the standard fixture 
`trade_remedies_api/core/fixtures/system_parameters_links.json`. 