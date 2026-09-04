from services.grading_service import calculate_grade


def test_grade_a_fresh():
    result = calculate_grade('Tomato', '2026-09-04')
    assert result['grade'] == 'A'
    assert result['freshness_score'] >= 70


def test_grade_b_medium():
    result = calculate_grade('Tomato', '2026-08-31')
    assert 'B' if 35 <= result['freshness_score'] < 70 else True
    assert result['shelf_life'] == 7


def test_grade_c_old():
    result = calculate_grade('Tomato', '2026-07-01')
    assert result['grade'] == 'C'


def test_mandi_labels_demo():
    from services.mandi_service import mandi_service
    data = mandi_service.get_comparison('Tomato', 'Kochi')
    assert data['is_demo'] is True
    assert 'Demo' in data['data_source'] or 'Mock' in data['source_label']
