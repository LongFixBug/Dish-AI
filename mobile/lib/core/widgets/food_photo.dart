import 'package:flutter/material.dart';

enum FoodPhotoMeal { comTam, caKho, bunGa }

class FoodPhoto extends StatelessWidget {
  const FoodPhoto({required this.meal, this.fit = BoxFit.cover, super.key});

  static const comTamAssetPath = 'assets/food/com-tam.png';
  static const caKhoAssetPath = 'assets/food/ca-kho.png';
  static const bunGaAssetPath = 'assets/food/bun-ga.png';

  final FoodPhotoMeal meal;
  final BoxFit fit;

  String get _assetPath => switch (meal) {
    FoodPhotoMeal.comTam => comTamAssetPath,
    FoodPhotoMeal.caKho => caKhoAssetPath,
    FoodPhotoMeal.bunGa => bunGaAssetPath,
  };

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      _assetPath,
      width: double.infinity,
      height: double.infinity,
      fit: fit,
    );
  }
}
