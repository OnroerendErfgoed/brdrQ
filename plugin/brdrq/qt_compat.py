from qgis.core import Qgis


IS_QGIS4 = Qgis.QGIS_VERSION_INT >= 40000


def dialog_exec(dialog):
    """
    Execute a dialog in a way that works for both QGIS 3 (Qt5) and QGIS 4 (Qt6).
    """
    return dialog.exec()


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
