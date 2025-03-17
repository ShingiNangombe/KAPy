# KAPy indicator configuration

*Configuration of indicators is set through a tab-separated table, with one row per indicator. The available configuration options are described here. All options are required*

## Properties

- **`id`** *(string, required)*: Identifier for the indicators. Must be unique.
- **`name`** *(string, required)*: Name of the indicator.
- **`units`** *(string, required)*: Units of measurement for the indicator.
- **`variables`**: List of input variables required to calculate the indicator. Must be at least one specified.
  - **One of**
    - *string*
    - *array*
      - **Items** *(string)*
- **`seasons`** *(string)*: Comma-separated lists of season IDs over which the indicator is to be calculated. IDs should match those in the [seasons configuration](seasons.md) table. In addition, `all` selects all seasons.
- **`time_binning`** *(string, required)*: Time bins over which indicators are calculated. In the case of choosing `periods`, the indicator will be calculated for all periods defined in the [periods configuration](periods.md) table. Indicators can also be calculated across a whole year, using the `years`options. Months were previously available, but have been removed. Must be one of: `["periods", "years"]`.
- **`statistic`** *(string, required)*: Statistic to be used to calculate the indicator. KAPy has three basic types of indicators built in. 1) `mean` calculates an average across the period. 2)`count` counts the number of days in the period above or below a threshold. Additional parameters must be supplied via the `additionalArgs` field: `threshold` is the threshold value, and `op` is the comparison operator - one of `>`,`gt`,`<`,`lt`,  `>=`, `ge`, `<=` or `le`.  3) `custom` calls the function defined in `customScriptPath` and `customScriptFunction` and utilised arguments supplied as a dictionary in `additionalArgs`. Must be one of: `["custom", "mean", "count"]`.
- **`additionalArgs`** *(string, required)*: Additional arbitrary arguments specified as a dict to be passed to the function via keyword arguments. e.g. `{'threshold':'25','op':'gt'}`. If no there are no additional parameters. an empty dict should be supplied i.e. `{}`.
- **`customScriptPath`** *(string, required)*: If `statistic` is set to `custom`, this field is used to identify the path to a custom script, if applicable.
- **`customScriptFunction`** *(string, required)*: Name of the function in `customScriptPath` to be used for calculating the indicator,  if applicable.
