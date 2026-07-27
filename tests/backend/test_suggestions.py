"""Hợp đồng xếp hạng món gợi ý — phần thuần, không chạm DB."""

import pytest

from backend.services.suggestions import (
    DishOption,
    NutritionBudget,
    conflicts_with_allergies,
    rank_dishes,
    remaining_budget,
)


def _dish(name, calories, protein, fat, carbs, grams=300.0):
    return DishOption(
        dish_name=name,
        grams=grams,
        calories=calories,
        protein_g=protein,
        fat_g=fat,
        carbs_g=carbs,
    )


def _budget(calories=600.0, protein=40.0, fat=20.0, carbs=60.0):
    return NutritionBudget(
        calories=calories, protein_g=protein, fat_g=fat, carbs_g=carbs
    )


class TestRemainingBudget:
    def test_tru_phan_da_an_khoi_muc_tieu(self):
        budget = remaining_budget(
            2000, 100, 60, 250, 1400, 70, 40, 180
        )

        assert budget.calories == 600
        assert budget.protein_g == 30
        assert budget.fat_g == 20
        assert budget.carbs_g == 70

    def test_an_vuot_muc_tieu_thi_ve_0_chu_khong_am(self):
        """Khoảng trống âm sẽ làm mọi phép so khớp bên dưới đảo chiều vô nghĩa."""
        budget = remaining_budget(1800, 90, 50, 200, 2400, 120, 80, 260)

        assert budget.calories == 0
        assert budget.protein_g == 0
        assert budget.fat_g == 0
        assert budget.carbs_g == 0


class TestAllergies:
    @pytest.mark.parametrize(
        ("dish", "allergy"),
        [
            ("Bún hải sản", "hải sản"),
            ("Cháo tôm", "tôm"),
            ("Bánh mì trứng ốp la", "trứng"),
            # Không dấu vẫn phải bắt được: người dùng gõ kiểu nào cũng có.
            ("Lẩu hải sản", "hai san"),
        ],
    )
    def test_bat_duoc_tu_khoa_di_ung_trong_ten_mon(self, dish, allergy):
        assert conflicts_with_allergies(dish, [allergy])

    def test_khong_bat_nham_mon_khong_lien_quan(self):
        assert not conflicts_with_allergies("Cơm tấm sườn", ["hải sản"])
        assert not conflicts_with_allergies("Phở bò", ["tôm"])

    def test_danh_sach_di_ung_rong_thi_khong_chan_gi(self):
        assert not conflicts_with_allergies("Bún hải sản", [])

    def test_mon_di_ung_bi_loai_khoi_ket_qua(self):
        results = rank_dishes(
            [
                _dish("Bún hải sản", 500, 30, 15, 60),
                _dish("Cơm gà", 520, 32, 16, 62),
            ],
            _budget(),
            allergies=["hải sản"],
        )

        assert [item.dish.dish_name for item in results] == ["Cơm gà"]


class TestRanking:
    def test_uu_tien_mon_lap_dung_macro_dang_thieu(self):
        """Thiếu đạm thì món giàu đạm phải thắng món toàn tinh bột."""
        results = rank_dishes(
            [
                _dish("Xôi ngọt", 500, 8, 10, 95),
                _dish("Ức gà áp chảo", 500, 55, 12, 30),
            ],
            _budget(calories=700, protein=60, fat=10, carbs=20),
        )

        assert results[0].dish.dish_name == "Ức gà áp chảo"

    def test_loai_mon_vuot_qua_khoang_calo_con_lai(self):
        results = rank_dishes(
            [
                _dish("Lẩu thập cẩm", 1400, 60, 50, 120),
                _dish("Canh rau", 180, 8, 4, 20),
            ],
            _budget(calories=400),
        )

        assert [item.dish.dish_name for item in results] == ["Canh rau"]

    def test_bo_qua_mon_vua_an_hom_nay(self):
        results = rank_dishes(
            [_dish("Cơm tấm", 500, 30, 18, 60), _dish("Phở bò", 480, 28, 12, 62)],
            _budget(),
            exclude_names=["cơm tấm"],
        )

        assert [item.dish.dish_name for item in results] == ["Phở bò"]

    def test_het_khau_phan_thi_khong_goi_y_gi(self):
        """Thà im lặng còn hơn đẩy người dùng ăn thêm khi đã chạm mục tiêu."""
        results = rank_dishes(
            [_dish("Cơm gà", 500, 30, 15, 60)],
            _budget(calories=40),
        )

        assert results == []

    def test_mon_khong_co_so_lieu_bi_bo_qua(self):
        results = rank_dishes(
            [_dish("Món chưa có dữ liệu", 0, 0, 0, 0)],
            _budget(),
        )

        assert results == []

    def test_ket_qua_on_dinh_giua_cac_lan_goi(self):
        dishes = [
            _dish("Món A", 400, 20, 10, 50),
            _dish("Món B", 400, 20, 10, 50),
            _dish("Món C", 400, 20, 10, 50),
        ]

        first = [item.dish.dish_name for item in rank_dishes(dishes, _budget())]
        second = [item.dish.dish_name for item in rank_dishes(dishes, _budget())]

        assert first == second

    def test_cat_dung_so_luong_yeu_cau(self):
        dishes = [_dish(f"Món {i}", 400, 20, 10, 50) for i in range(10)]

        assert len(rank_dishes(dishes, _budget(), limit=3)) == 3


class TestPreferences:
    def test_nhieu_dam_day_mon_giau_dam_len(self):
        dishes = [
            _dish("Cơm chiên", 500, 12, 20, 70),
            _dish("Gà nướng", 500, 45, 18, 35),
        ]
        budget = _budget(calories=700, protein=30, fat=25, carbs=70)

        without = rank_dishes(dishes, budget)
        with_pref = rank_dishes(dishes, budget, preferences=["Nhiều đạm"])

        chicken_before = next(
            i.score for i in without if i.dish.dish_name == "Gà nướng"
        )
        chicken_after = next(
            i.score for i in with_pref if i.dish.dish_name == "Gà nướng"
        )
        assert chicken_after > chicken_before

    def test_it_dau_phat_mon_nhieu_mo(self):
        # 30g béo trên 400 kcal → 67% calo từ chất béo.
        greasy = _dish("Thịt quay", 400, 15, 30, 15)
        budget = _budget(calories=600)

        without = rank_dishes([greasy], budget)[0].score
        with_pref = rank_dishes([greasy], budget, preferences=["Ít dầu"])[0].score

        assert with_pref < without


class TestReason:
    def test_luon_noi_ro_calo_va_phan_dam_bu_duoc(self):
        results = rank_dishes(
            [_dish("Ức gà", 500, 50, 10, 30)],
            _budget(calories=700, protein=60, fat=15, carbs=40),
        )

        reason = results[0].reason
        assert "500 kcal" in reason
        assert "700 kcal" in reason
        assert "đạm" in reason
