"""FarmBridge route blueprints package."""

from flask import Blueprint, g


def user_context():
    return {
        'user_id': getattr(g, 'user_id', None),
        'phone': getattr(g, 'phone', None),
        'role': getattr(g, 'role', 'consumer'),
        'name': getattr(g, 'name', None),
    }
