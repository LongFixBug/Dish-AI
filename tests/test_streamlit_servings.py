"""Regression test cho control khẩu phần riêng từng món trên Streamlit."""

from streamlit.testing.v1 import AppTest


def test_streamlit_adjusts_each_dish_independently() -> None:
    result = {
        "source": "vision",
        "dish_name": "Cơm sườn + Canh cải trắng",
        "dishes": [],
        "nutrition": {
            "items": [
                {
                    "item_name": "Cơm sườn",
                    "grams": 350.0,
                    "calories": 539.0,
                    "protein_g": 21.4,
                    "fat_g": 14.2,
                    "carbs_g": 81.4,
                    "fiber_g": 0.7,
                    "found_in_db": True,
                },
                {
                    "item_name": "Canh cải trắng",
                    "grams": 150.0,
                    "calories": 45.0,
                    "protein_g": 2.0,
                    "fat_g": 1.0,
                    "carbs_g": 8.0,
                    "fiber_g": 1.0,
                    "found_in_db": False,
                },
            ],
            "confidence_score": 0.5,
            "missing_ingredients": [],
        },
    }

    app = AppTest.from_file("streamlit_app.py").run(timeout=10)
    app.session_state["analyze_result"] = result
    app.run(timeout=10)

    assert [(widget.label, widget.value) for widget in app.number_input] == [
        ("Khẩu phần Cơm sườn", 350.0),
        ("Khẩu phần Canh cải trắng", 150.0),
    ]
    assert [widget.value for widget in app.selectbox] == ["g", "ml"]

    app.number_input[0].set_value(700.0)
    app.run(timeout=10)

    assert app.number_input[0].value == 700.0
    assert app.number_input[1].value == 150.0
    assert app.metric[0].value == "1123 kcal"
    assert not list(app.exception)
