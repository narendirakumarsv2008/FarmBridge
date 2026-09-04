"""Mandi benchmark and AI grading routes."""

from flask import Blueprint, request

from services.crop_parser import extract_crop_name_smart
from services.grading_service import calculate_grade
from services.mandi_service import mandi_service
from utils.responses import success, validation_error

bp = Blueprint('mandi', __name__)


@bp.route('/api/mandi-price', methods=['GET'])
def mandi_price():
    crop = request.args.get('crop', '').strip()
    location = request.args.get('location', '').strip()
    smart = extract_crop_name_smart(crop)
    if smart:
        crop = smart.lower()
    result = mandi_service.get_comparison(crop, location)
    return success(result)


@bp.route('/api/grade', methods=['POST'])
def grade():
    data = request.json or {}
    crop_name = data.get('crop_name', '')
    harvest_date = data.get('harvest_date', '')
    photo = data.get('photo', None)
    if not crop_name or not harvest_date:
        return validation_error('crop_name and harvest_date required')
    smart = extract_crop_name_smart(crop_name)
    if smart:
        crop_name = smart
    result = calculate_grade(crop_name, harvest_date, photo)
    return success(result)
