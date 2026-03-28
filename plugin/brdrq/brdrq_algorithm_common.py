from brdr.aligner import Aligner
from brdr.configs import AlignerConfig, ProcessorConfig
from brdr.enums import PredictionStrategy
from qgis.core import (
    QgsProcessing,
    QgsProcessingFeatureSourceDefinition,
    QgsProcessingOutputVectorLayer,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterFile,
    QgsProcessingParameterNumber,
    QgsProject,
)


def get_log_feedback(show_log_info, feedback):
    return feedback if show_log_info else None


def build_processor(
    processor_enum,
    od_strategy,
    snap_strategy,
    multi_as_single_modus,
    correction_distance,
    threshold_overlap_percentage,
    get_processor_by_id_fn,
):
    processor_config = ProcessorConfig()
    processor_config.od_strategy = od_strategy
    processor_config.snap_strategy = snap_strategy
    processor_config.multi_as_single_modus = multi_as_single_modus
    processor_config.correction_distance = correction_distance
    processor_config.threshold_overlap_percentage = threshold_overlap_percentage
    return get_processor_by_id_fn(
        processor_id=processor_enum.value, config=processor_config
    )


def build_aligner(
    feedback,
    crs,
    processor,
    log_metadata,
    add_observations,
):
    aligner_config = AlignerConfig()
    aligner_config.log_metadata = log_metadata
    aligner_config.add_observations = add_observations
    return Aligner(
        feedback=feedback,
        crs=crs,
        processor=processor,
        config=aligner_config,
    )


def get_prediction_strategy_options(prediction_strategy):
    if prediction_strategy == PredictionStrategy.BEST:
        return 1, True
    if prediction_strategy == PredictionStrategy.ALL:
        return -1, False
    if prediction_strategy == PredictionStrategy.ORIGINAL:
        return 1, False
    raise Exception("Unknown PREDICTION_STRATEGY")


def resolve_thematic_layer_and_crs(
    algorithm,
    default_theme_layer,
    parameters,
    input_thematic,
    context,
):
    if isinstance(default_theme_layer, QgsProcessingFeatureSourceDefinition):
        layer_thematic = default_theme_layer
        crs = (
            QgsProject.instance()
            .mapLayer(default_theme_layer.toVariant()["source"]["val"])
            .sourceCrs()
            .authid()
        )
    else:
        layer_thematic = algorithm.parameterAsVectorLayer(
            parameters, input_thematic, context
        )
        crs = layer_thematic.sourceCrs().authid()
    return layer_thematic, crs


def initialize_default_attributes(instance, mapping):
    """
    mapping: iterable of tuples (attribute_name, key_in_params_default_dict)
    """
    for attr_name, default_key in mapping:
        setattr(instance, attr_name, instance.params_default_dict[default_key])


def apply_saved_settings(instance, prefix, settings_spec, read_setting_fn):
    """
    settings_spec: iterable of tuples
      (attribute_name, setting_key[, cast_fn[, scope]])
    """
    for spec in settings_spec:
        attr_name = spec[0]
        setting_key = spec[1]
        cast_fn = spec[2] if len(spec) > 2 else None
        scope = spec[3] if len(spec) > 3 else "auto"

        value = read_setting_fn(
            prefix,
            setting_key,
            getattr(instance, attr_name),
            scope=scope,
        )
        if cast_fn is not None:
            value = cast_fn(value)
        setattr(instance, attr_name, value)


def write_saved_settings(instance, prefix, settings_spec, write_setting_fn):
    """
    settings_spec: iterable of tuples
      (attribute_name, setting_key[, scope])
    """
    for spec in settings_spec:
        attr_name = spec[0]
        setting_key = spec[1]
        scope = spec[2] if len(spec) > 2 else "both"
        write_setting_fn(prefix, setting_key, getattr(instance, attr_name), scope=scope)


def assign_parameter_values(instance, parameters, param_to_attr_map):
    """
    param_to_attr_map: iterable of tuples (attribute_name, parameter_key)
    """
    for attr_name, parameter_key in param_to_attr_map:
        setattr(instance, attr_name, parameters[parameter_key])


def _add_parameter(algorithm, parameter, advanced=False):
    flags = parameter.flags()
    if advanced:
        flags = flags | QgsProcessingParameterDefinition.FlagAdvanced
    parameter.setFlags(flags)
    algorithm.addParameter(parameter)


def add_feature_source_parameter(
    algorithm,
    name,
    description,
    geometry_types,
    default_value,
    optional=False,
    advanced=False,
):
    parameter = QgsProcessingParameterFeatureSource(
        name,
        description,
        geometry_types,
        defaultValue=default_value,
        optional=optional,
    )
    _add_parameter(algorithm, parameter, advanced=advanced)


def add_field_parameter(
    algorithm,
    name,
    description,
    default_value,
    parent_layer_parameter_name,
    optional=False,
    advanced=False,
):
    parameter = QgsProcessingParameterField(
        name,
        description,
        defaultValue=default_value,
        parentLayerParameterName=parent_layer_parameter_name,
        optional=optional,
    )
    _add_parameter(algorithm, parameter, advanced=advanced)


def add_enum_parameter(
    algorithm,
    name,
    description,
    options,
    default_value,
    advanced=False,
):
    parameter = QgsProcessingParameterEnum(
        name,
        description,
        options=options,
        defaultValue=default_value,
    )
    _add_parameter(algorithm, parameter, advanced=advanced)


def add_number_parameter(
    algorithm,
    name,
    description,
    number_type,
    default_value,
    optional=False,
    min_value=None,
    max_value=None,
    advanced=False,
):
    kwargs = {
        "type": number_type,
        "defaultValue": default_value,
        "optional": optional,
    }
    if min_value is not None:
        kwargs["minValue"] = min_value
    if max_value is not None:
        kwargs["maxValue"] = max_value
    parameter = QgsProcessingParameterNumber(name, description, **kwargs)
    _add_parameter(algorithm, parameter, advanced=advanced)


def add_file_parameter(
    algorithm,
    name,
    description,
    behavior,
    default_value,
    optional=True,
    advanced=False,
):
    parameter = QgsProcessingParameterFile(
        name,
        description,
        behavior=behavior,
        defaultValue=default_value,
        optional=optional,
    )
    _add_parameter(algorithm, parameter, advanced=advanced)


def add_boolean_parameter(
    algorithm,
    name,
    description,
    default_value,
    advanced=False,
):
    parameter = QgsProcessingParameterBoolean(
        name,
        description,
        defaultValue=default_value,
    )
    _add_parameter(algorithm, parameter, advanced=advanced)


def add_standard_result_outputs(
    algorithm,
    layer_result,
    layer_result_diff,
    layer_result_diff_plus,
    layer_result_diff_min,
    layer_correction,
):
    algorithm.addOutput(
        QgsProcessingOutputVectorLayer(
            "OUTPUT_RESULT",
            layer_result,
            QgsProcessing.TypeVectorAnyGeometry,
        )
    )
    algorithm.addOutput(
        QgsProcessingOutputVectorLayer(
            "OUTPUT_RESULT_DIFF",
            layer_result_diff,
            QgsProcessing.TypeVectorAnyGeometry,
        )
    )
    algorithm.addOutput(
        QgsProcessingOutputVectorLayer(
            "OUTPUT_RESULT_DIFF_PLUS",
            layer_result_diff_plus,
            QgsProcessing.TypeVectorAnyGeometry,
        )
    )
    algorithm.addOutput(
        QgsProcessingOutputVectorLayer(
            "OUTPUT_RESULT_DIFF_MIN",
            layer_result_diff_min,
            QgsProcessing.TypeVectorAnyGeometry,
        )
    )
    algorithm.addOutput(
        QgsProcessingOutputVectorLayer(
            "OUTPUT_CORRECTION",
            layer_correction,
            QgsProcessing.TypeVectorAnyGeometry,
        )
    )
