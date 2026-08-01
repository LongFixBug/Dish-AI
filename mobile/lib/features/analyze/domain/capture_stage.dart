enum CaptureStage {
  ready,
  review,
  analyzing;

  bool get isAnalyzing => this == CaptureStage.analyzing;
}
