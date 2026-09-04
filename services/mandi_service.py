"""
Live Mandi comparison service.

The current implementation uses a stable, clearly-labelled demo benchmark so
the UI works without a third-party API. It is NOT real eNAM data. The provider
abstraction makes replacing it with eNAM / Agmarknet / a market data provider
straightforward.
"""

import random
from datetime import datetime

from services.crop_parser import extract_crop_name_smart

DEMO_LABEL = 'Demo Market Benchmark'
ESTIMATED_LABEL = 'Estimated Market Price'
MOCK_SOURCE_LABEL = 'Mock Mandi Data'

_MOCK_MANDI_PRICES = {
    'tomato': {'price': 22, 'mandi': 'Azadpur Mandi, Delhi', 'trend': '+2.3%'},
    'potato': {'price': 18, 'mandi': 'Agra Mandi, UP', 'trend': '-0.5%'},
    'onion': {'price': 28, 'mandi': 'Lasalgaon Mandi, MH', 'trend': '+5.1%'},
    'wheat': {'price': 24, 'mandi': 'Karnal Mandi, HR', 'trend': '+1.2%'},
    'rice': {'price': 35, 'mandi': 'Karnal Mandi, HR', 'trend': '+0.8%'},
    'mango': {'price': 60, 'mandi': 'Vashi Mandi, MH', 'trend': '+8.2%'},
    'banana': {'price': 25, 'mandi': 'Jalgaon Mandi, MH', 'trend': '+1.5%'},
    'cabbage': {'price': 15, 'mandi': 'Bangalore APMC', 'trend': '-1.2%'},
    'cauliflower': {'price': 20, 'mandi': 'Kolkata Mandi', 'trend': '+3.4%'},
    'brinjal': {'price': 26, 'mandi': 'Chennai Koyambedu', 'trend': '+2.1%'},
    'carrot': {'price': 30, 'mandi': 'Ooty Mandi, TN', 'trend': '+0.9%'},
    'chilli': {'price': 45, 'mandi': 'Guntur Mandi, AP', 'trend': '+6.7%'},
    'grapes': {'price': 55, 'mandi': 'Nashik Mandi, MH', 'trend': '+4.2%'},
}


class MarketDataProvider:
    """Future integration point for real market data."""

    name = 'base'

    def get_price(self, crop, location=None):
        raise NotImplementedError


class MockMandiProvider(MarketDataProvider):
    name = 'mock'

    def get_price(self, crop, location=None):
        key = (crop or '').lower().strip()
        info = None
        for k, v in _MOCK_MANDI_PRICES.items():
            if k in key or key in k:
                info = v
                break
        if not info:
            today = datetime.now().strftime('%Y-%m-%d')
            rnd = random.Random('%s-%s-%s' % (crop, location, today))
            base = rnd.randint(18, 45)
            info = {
                'price': base,
                'mandi': 'Nearest APMC - %s' % (location[:20] if location else 'Local Mandi'),
                'trend': '%s%.1f%%' % ('+' if rnd.random() > 0.3 else '-', rnd.uniform(0.5, 6.0)),
            }
        return info


class ENAMProvider(MarketDataProvider):
    """Placeholder future integration with real eNAM/Agmarknet data.

    A real implementation would call the market API, cache results, and return
    the same structure. Nothing here is wired to a live feed yet.
    """

    name = 'enam'


class MandiService:
    def __init__(self, provider=None):
        self.provider = provider or MockMandiProvider()

    def get_comparison(self, crop, location=''):
        smart = extract_crop_name_smart(crop)
        if smart:
            crop = smart.lower()
        info = self.provider.get_price(crop, location)
        uplift = random.Random('%s-%s' % (crop, datetime.now().strftime('%Y-%m-%d'))).uniform(0.15, 0.25)
        platform_price = round(float(info['price']) * (1 + uplift), 2)
        return {
            'crop': crop,
            'mandi_price': float(info['price']),
            'mandi_name': info['mandi'],
            'mandi_trend': info['trend'],
            'platform_price': platform_price,
            'uplift_percent': round(uplift * 100, 1),
            'extra_earning_per_kg': round(platform_price - info['price'], 2),
            'extra_earning_per_quintal': round((platform_price - info['price']) * 100, 2),
            'comparison': {'mandi': info['price'], 'platform': platform_price},
            # Explicitly label the data as a demo / estimated benchmark.
            'data_source': DEMO_LABEL,
            'source_label': MOCK_SOURCE_LABEL,
            'is_demo': True,
            'provider': self.provider.name,
        }


mandi_service = MandiService()
