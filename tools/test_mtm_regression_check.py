import tools.mtm_regression_check as regression_check


def _model(lock_status, fields=None, locked=True):
    return {
        "model": "test_model",
        "display_name": "Test Model",
        "equipment_type": "compact_track_loader",
        "lock_status": lock_status,
        "locked": locked,
        "fields": fields or {
            "horsepower_hp": 74,
            "operating_weight_lbs": 9500,
        },
    }


def test_pending_allows_null_fields():
    status, failures = regression_check.validate_lock_entry(_model(
        "PENDING",
        fields={
            "horsepower_hp": 74,
            "hinge_pin_height_in": None,
        },
    ))
    assert status == "PENDING"
    assert failures == []


def test_ready_for_lock_rejects_null_fields():
    status, failures = regression_check.validate_lock_entry(_model(
        "READY_FOR_LOCK",
        fields={
            "horsepower_hp": 74,
            "hinge_pin_height_in": None,
        },
    ))
    assert status == "READY_FOR_LOCK"
    assert failures == [
        (
            "hinge_pin_height_in",
            "lock file value is null but lock_status=READY_FOR_LOCK; fill all fields before promotion",
        )
    ]


def test_locked_rejects_null_fields_before_enforcement():
    status, failures = regression_check.validate_lock_entry(_model(
        "LOCKED",
        fields={
            "horsepower_hp": 74,
            "hinge_pin_height_in": None,
        },
    ))
    assert status == "LOCKED"
    assert failures == [
        (
            "hinge_pin_height_in",
            "lock file value is null but lock_status=LOCKED; fill all fields before promotion",
        )
    ]


def test_legacy_locked_entry_with_nulls_downgrades_to_pending():
    status = regression_check.get_lock_status({
        "locked": True,
        "fields": {
            "horsepower_hp": 74,
            "hinge_pin_height_in": None,
        },
    })
    assert status == "PENDING"

