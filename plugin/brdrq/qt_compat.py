from qgis.core import Qgis


IS_QGIS4 = Qgis.QGIS_VERSION_INT >= 40000


def dialog_exec(dialog):
    """
    Execute a dialog in a way that works for both QGIS 3 (Qt5) and QGIS 4 (Qt6).
    """
    return dialog.exec()


def qmessagebox_warning_icon():
    from qgis.PyQt.QtWidgets import QMessageBox

    value = getattr(QMessageBox, "Warning", None)
    if value is not None:
        return value

    icon = getattr(QMessageBox, "Icon", None)
    if icon is not None and hasattr(icon, "Warning"):
        return icon.Warning

    raise AttributeError("QMessageBox Warning icon enum not available")


def qmessagebox_critical_icon():
    from qgis.PyQt.QtWidgets import QMessageBox

    value = getattr(QMessageBox, "Critical", None)
    if value is not None:
        return value

    icon = getattr(QMessageBox, "Icon", None)
    if icon is not None and hasattr(icon, "Critical"):
        return icon.Critical

    raise AttributeError("QMessageBox Critical icon enum not available")


def qmessagebox_ok_button():
    from qgis.PyQt.QtWidgets import QMessageBox

    value = getattr(QMessageBox, "Ok", None)
    if value is not None:
        return value

    standard_button = getattr(QMessageBox, "StandardButton", None)
    if standard_button is not None and hasattr(standard_button, "Ok"):
        return standard_button.Ok

    raise AttributeError("QMessageBox Ok button enum not available")


def set_map_layer_combo_filters(combo, filters):
    """
    Compatibility wrapper for QgsMapLayerComboBox filter API changes.
    """
    if hasattr(combo, "setFilter"):
        combo.setFilter(filters)
        return
    if hasattr(combo, "setFilters"):
        combo.setFilters(filters)
        return
    raise AttributeError("QgsMapLayerComboBox has no setFilters/setFilter method")


def map_layer_proxy_filter_flag(name):
    """
    Resolve QgsMapLayerProxyModel filter flags across QGIS 3/4 enum API variants.
    """
    from qgis.core import QgsMapLayerProxyModel

    direct = getattr(QgsMapLayerProxyModel, name, None)
    if direct is not None:
        return direct

    for enum_container_name in ("Filter", "Filters"):
        enum_container = getattr(QgsMapLayerProxyModel, enum_container_name, None)
        if enum_container is None:
            continue
        candidate = getattr(enum_container, name, None)
        if candidate is not None:
            return candidate

    raise AttributeError(f"Unsupported QgsMapLayerProxyModel filter flag: {name}")


def map_layer_filter_polygon():
    return map_layer_proxy_filter_flag("PolygonLayer")


def map_layer_filter_line():
    return map_layer_proxy_filter_flag("LineLayer")


def map_layer_filter_point():
    return map_layer_proxy_filter_flag("PointLayer")


def qt_right_dock_widget_area():
    from qgis.PyQt.QtCore import Qt

    value = getattr(Qt, "RightDockWidgetArea", None)
    if value is not None:
        return value

    dock_widget_area = getattr(Qt, "DockWidgetArea", None)
    if dock_widget_area is not None and hasattr(
        dock_widget_area, "RightDockWidgetArea"
    ):
        return dock_widget_area.RightDockWidgetArea

    raise AttributeError("Qt RightDockWidgetArea enum not available")


def qt_wait_cursor():
    from qgis.PyQt.QtCore import Qt

    value = getattr(Qt, "WaitCursor", None)
    if value is not None:
        return value

    cursor_shape = getattr(Qt, "CursorShape", None)
    if cursor_shape is not None and hasattr(cursor_shape, "WaitCursor"):
        return cursor_shape.WaitCursor

    raise AttributeError("Qt WaitCursor enum not available")


def qt_scrollbar_as_needed():
    """
    Cross-Qt helper for Qt.ScrollBarAsNeeded enum location differences.
    """
    from qgis.PyQt.QtCore import Qt

    value = getattr(Qt, "ScrollBarAsNeeded", None)
    if value is not None:
        return value

    scroll_bar_policy = getattr(Qt, "ScrollBarPolicy", None)
    if scroll_bar_policy is not None and hasattr(
        scroll_bar_policy, "ScrollBarAsNeeded"
    ):
        return scroll_bar_policy.ScrollBarAsNeeded

    raise AttributeError("Qt ScrollBarAsNeeded enum not available")


def qt_scrollbar_always_off():
    """
    Cross-Qt helper for Qt.ScrollBarAlwaysOff enum location differences.
    """
    from qgis.PyQt.QtCore import Qt

    value = getattr(Qt, "ScrollBarAlwaysOff", None)
    if value is not None:
        return value

    scroll_bar_policy = getattr(Qt, "ScrollBarPolicy", None)
    if scroll_bar_policy is not None and hasattr(
        scroll_bar_policy, "ScrollBarAlwaysOff"
    ):
        return scroll_bar_policy.ScrollBarAlwaysOff

    raise AttributeError("Qt ScrollBarAlwaysOff enum not available")


def qt_frame_no_frame():
    """
    Cross-Qt helper for QFrame.NoFrame enum location differences.
    """
    from qgis.PyQt import QtWidgets

    value = getattr(QtWidgets.QFrame, "NoFrame", None)
    if value is not None:
        return value

    frame_shape = getattr(QtWidgets.QFrame, "Shape", None)
    if frame_shape is not None and hasattr(frame_shape, "NoFrame"):
        return frame_shape.NoFrame

    raise AttributeError("Qt QFrame.NoFrame enum not available")


def qt_size_policy_preferred():
    """
    Cross-Qt helper for QSizePolicy.Preferred enum location differences.
    """
    from qgis.PyQt import QtWidgets

    value = getattr(QtWidgets.QSizePolicy, "Preferred", None)
    if value is not None:
        return value

    policy = getattr(QtWidgets.QSizePolicy, "Policy", None)
    if policy is not None and hasattr(policy, "Preferred"):
        return policy.Preferred

    raise AttributeError("Qt QSizePolicy.Preferred enum not available")


def qt_size_policy_fixed():
    """
    Cross-Qt helper for QSizePolicy.Fixed enum location differences.
    """
    from qgis.PyQt import QtWidgets

    value = getattr(QtWidgets.QSizePolicy, "Fixed", None)
    if value is not None:
        return value

    policy = getattr(QtWidgets.QSizePolicy, "Policy", None)
    if policy is not None and hasattr(policy, "Fixed"):
        return policy.Fixed

    raise AttributeError("Qt QSizePolicy.Fixed enum not available")


def qt_tool_button_text_only():
    """
    Cross-Qt helper for Qt.ToolButtonTextOnly enum location differences.
    """
    from qgis.PyQt.QtCore import Qt

    value = getattr(Qt, "ToolButtonTextOnly", None)
    if value is not None:
        return value

    style = getattr(Qt, "ToolButtonStyle", None)
    if style is not None and hasattr(style, "ToolButtonTextOnly"):
        return style.ToolButtonTextOnly

    raise AttributeError("Qt ToolButtonTextOnly enum not available")


def qt_align_left():
    """
    Cross-Qt helper for Qt.AlignLeft enum location differences.
    """
    from qgis.PyQt.QtCore import Qt

    value = getattr(Qt, "AlignLeft", None)
    if value is not None:
        return value

    alignment_flag = getattr(Qt, "AlignmentFlag", None)
    if alignment_flag is not None and hasattr(alignment_flag, "AlignLeft"):
        return alignment_flag.AlignLeft

    raise AttributeError("Qt AlignLeft enum not available")


def qt_no_focus():
    """
    Cross-Qt helper for Qt.NoFocus enum location differences.
    """
    from qgis.PyQt.QtCore import Qt

    value = getattr(Qt, "NoFocus", None)
    if value is not None:
        return value

    focus_policy = getattr(Qt, "FocusPolicy", None)
    if focus_policy is not None and hasattr(focus_policy, "NoFocus"):
        return focus_policy.NoFocus

    raise AttributeError("Qt NoFocus enum not available")


def _qabstract_item_view_enum(name, *containers):
    from qgis.PyQt import QtWidgets

    direct = getattr(QtWidgets.QAbstractItemView, name, None)
    if direct is not None:
        return direct

    for container_name in containers:
        container = getattr(QtWidgets.QAbstractItemView, container_name, None)
        if container is None:
            continue
        candidate = getattr(container, name, None)
        if candidate is not None:
            return candidate

    raise AttributeError(f"QAbstractItemView enum not available: {name}")


def qt_item_view_select_rows():
    return _qabstract_item_view_enum("SelectRows", "SelectionBehavior")


def qt_item_view_single_selection():
    return _qabstract_item_view_enum("SingleSelection", "SelectionMode")


def qt_item_view_no_edit_triggers():
    return _qabstract_item_view_enum("NoEditTriggers", "EditTrigger")


def qt_item_view_scroll_per_pixel():
    return _qabstract_item_view_enum("ScrollPerPixel", "ScrollMode")


def _qheader_view_enum(name):
    from qgis.PyQt import QtWidgets

    direct = getattr(QtWidgets.QHeaderView, name, None)
    if direct is not None:
        return direct

    resize_mode = getattr(QtWidgets.QHeaderView, "ResizeMode", None)
    if resize_mode is not None and hasattr(resize_mode, name):
        return getattr(resize_mode, name)

    raise AttributeError(f"QHeaderView enum not available: {name}")


def qt_header_resize_to_contents():
    return _qheader_view_enum("ResizeToContents")


def qt_header_stretch():
    return _qheader_view_enum("Stretch")


def qt_header_fixed():
    return _qheader_view_enum("Fixed")


def qt_header_interactive():
    return _qheader_view_enum("Interactive")


def qt_item_is_editable():
    """
    Cross-Qt helper for Qt.ItemIsEditable enum location differences.
    """
    from qgis.PyQt.QtCore import Qt

    value = getattr(Qt, "ItemIsEditable", None)
    if value is not None:
        return value

    item_flag = getattr(Qt, "ItemFlag", None)
    if item_flag is not None and hasattr(item_flag, "ItemIsEditable"):
        return item_flag.ItemIsEditable

    raise AttributeError("Qt ItemIsEditable enum not available")


def qt_user_role():
    """
    Cross-Qt helper for Qt.UserRole enum location differences.
    """
    from qgis.PyQt.QtCore import Qt

    value = getattr(Qt, "UserRole", None)
    if value is not None:
        return value

    item_data_role = getattr(Qt, "ItemDataRole", None)
    if item_data_role is not None and hasattr(item_data_role, "UserRole"):
        return item_data_role.UserRole

    raise AttributeError("Qt UserRole enum not available")


def qt_checkstate_checked():
    from qgis.PyQt.QtCore import Qt

    value = getattr(Qt, "Checked", None)
    if value is not None:
        return value

    check_state = getattr(Qt, "CheckState", None)
    if check_state is not None and hasattr(check_state, "Checked"):
        return check_state.Checked

    raise AttributeError("Qt Checked enum not available")


def qt_checkstate_unchecked():
    from qgis.PyQt.QtCore import Qt

    value = getattr(Qt, "Unchecked", None)
    if value is not None:
        return value

    check_state = getattr(Qt, "CheckState", None)
    if check_state is not None and hasattr(check_state, "Unchecked"):
        return check_state.Unchecked

    raise AttributeError("Qt Unchecked enum not available")


def is_return_or_enter_key(key):
    """
    Cross-Qt helper for Return/Enter key detection.
    """
    from qgis.PyQt.QtCore import Qt

    candidates = []
    for name in ("Key_Return", "Key_Enter"):
        value = getattr(Qt, name, None)
        if value is not None:
            candidates.append(value)

    qt_key_enum = getattr(Qt, "Key", None)
    if qt_key_enum is not None:
        for name in ("Key_Return", "Key_Enter"):
            value = getattr(qt_key_enum, name, None)
            if value is not None:
                candidates.append(value)

    return key in candidates


def map_mouse_event_xy(event):
    """
    Return screen x/y from QgsMapMouseEvent across QGIS 3/4.
    """
    if hasattr(event, "x") and hasattr(event, "y"):
        return int(event.x()), int(event.y())

    if hasattr(event, "position"):
        pos = event.position()
        return int(pos.x()), int(pos.y())

    if hasattr(event, "pos"):
        pos = event.pos()
        return int(pos.x()), int(pos.y())

    raise AttributeError("Unsupported mouse event API: cannot extract x/y")


def map_mouse_event_pos(event):
    """
    Return a QPoint-like screen position from QgsMapMouseEvent across QGIS 3/4.
    """
    if hasattr(event, "position"):
        pos = event.position()
        # Qt6 can return QPointF; convert to integer QPoint when available.
        if hasattr(pos, "toPoint"):
            return pos.toPoint()
        return pos

    if hasattr(event, "pos"):
        return event.pos()

    raise AttributeError("Unsupported mouse event API: cannot extract pos")


def get_vector_menu(iface):
    """
    Get the Vector menu from QgsInterface with safe fallbacks for API differences.
    """
    if hasattr(iface, "vectorMenu"):
        menu = iface.vectorMenu()
        if menu is not None:
            return menu

    # Fallback for interfaces exposing menu by attribute instead of method.
    menu = getattr(iface, "vector_menu", None)
    if menu is not None:
        return menu

    # Last fallback: attach to plugin menu container if available.
    if hasattr(iface, "pluginMenu"):
        menu = iface.pluginMenu()
        if menu is not None:
            return menu

    return None


def remove_plugin_menu_action(iface, plugin_name, action):
    """
    Remove an action from plugin menu using whichever iface API is available.
    """
    if hasattr(iface, "removePluginMenu"):
        iface.removePluginMenu(plugin_name, action)
        return

    if hasattr(iface, "removePluginVectorMenu"):
        iface.removePluginVectorMenu(plugin_name, action)


def qgs_field_type_string():
    """
    Field type helper compatible with QGIS 3 (Qt5) and QGIS 4 (Qt6).
    """
    try:
        from qgis.PyQt.QtCore import QMetaType

        return QMetaType.Type.QString
    except Exception:
        from qgis.PyQt.QtCore import QVariant

        return QVariant.String


def qgs_field_type_double():
    """
    Field type helper compatible with QGIS 3 (Qt5) and QGIS 4 (Qt6).
    """
    try:
        from qgis.PyQt.QtCore import QMetaType

        return QMetaType.Type.Double
    except Exception:
        from qgis.PyQt.QtCore import QVariant

        return QVariant.Double
