from __future__ import annotations


def apply_ui_action(app, action_kind: str, action_data):
    if action_kind == "preview_frame":
        app.handle_preview_frame(action_data)
    elif action_kind == "preview_status":
        app.handle_preview_status(action_data)
    elif action_kind == "preview_stopped":
        app.handle_preview_stopped()
    elif action_kind == "capture_done":
        app.handle_capture_done()


def process_queue_once(ui_queue, capture_state, process_ui_message_fn, dispatch_ui_action_fn):
    kind, data, tag = ui_queue.get_nowait()
    snapshot = capture_state.queue_snapshot()
    action = process_ui_message_fn(snapshot, kind, data)
    capture_state.apply_queue_snapshot(snapshot)
    if action is not None:
        action_kind, action_data = action
        dispatch_ui_action_fn(action_kind, action_data)
