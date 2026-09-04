"""Blueprint registration."""

from routes import (
    auth,
    consumer,
    farmer,
    listings,
    misc,
    orders,
    pools,
    subscriptions,
)


def register_blueprints(app):
    for bp in (
        auth.bp,
        farmer.bp,
        consumer.bp,
        listings.bp,
        orders.bp,
        pools.bp,
        subscriptions.bp,
        misc.bp,
    ):
        app.register_blueprint(bp)
