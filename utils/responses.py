"""Consistent JSON API responses."""

from flask import jsonify


def success(data=None, status=200, meta=None):
    payload = {'success': True}
    if data is not None:
        payload['data'] = data
    if meta is not None:
        payload['meta'] = meta
    return jsonify(payload), status


def error(message, code='ERROR', status=400, details=None):
    err = {'code': code, 'message': message}
    if details:
        err['details'] = details
    return jsonify({'success': False, 'error': err}), status


def validation_error(message, details=None):
    return error(message, code='VALIDATION_ERROR', status=400, details=details)


def not_found(message='Not found'):
    return error(message, code='NOT_FOUND', status=404)


def unauth(message='Authentication required'):
    return error(message, code='UNAUTHORIZED', status=401)


def forbidden(message='Forbidden'):
    return error(message, code='FORBIDDEN', status=403)


def conflict(message):
    return error(message, code='CONFLICT', status=409)


def server_error(message='Internal server error'):
    return error(message, code='INTERNAL_ERROR', status=500)
