### 8. Top-1/Top-2 Margin Thresholding

  Vị trí: backend/services/recognition_cascade.py:39

  Công thức:

  margin = score(top-1) - score(top-2)

  Chỉ chốt kết quả khi:

  top1_score ≥ threshold
  và
  top1_score - top2_score ≥ margin_threshold

  Cách nói:

  > “Project dùng confidence threshold kết hợp top-1/top-2 margin để selective prediction: chỉ tự
  > động trả kết quả khi mô hình vừa tự tin vừa phân biệt rõ ứng viên thứ hai.”

  Ẩn dụ: học sinh được 9 điểm chưa đủ; đáp án thứ hai cũng phải thua đủ xa thì hệ thống mới thật sự
  tin.

  ———

  ### 9. U²-Net — Image Segmentation

  Vị trí: ml/serving/segment_server.py:148

  Project dùng rembg với model u2net để:

  - Phân đoạn chủ thể món ăn khỏi nền.
  - Tạo alpha mask.
  - Crop sát chủ thể.
  - Thêm viền trắng.
  - Xuất sticker PNG nền trong suốt.

  Cách nói:

  > “Project sử dụng U²-Net thông qua rembg để thực hiện foreground segmentation và tạo sticker món
  > ăn.”

  Nó phục vụ giao diện, không phải thuật toán chính để nhận diện món.

  ———

  ## B. Huấn luyện mô hình

  ### 10. Cross-Entropy Loss

  Vị trí: ml/training/train.py:510

  Đây là loss cho bài toán phân loại nhiều lớp. Khi model đặt xác suất thấp cho nhãn đúng, nó bị
  phạt.

  Cách nói:

  > “EfficientNet-B0 được huấn luyện bằng multi-class cross-entropy loss.”

  ———

  ### 11. Class-weighted Cross-Entropy

  Vị trí: ml/training/train.py:187

  Công thức:

  weight[c] = tổng số ảnh / (số class × số ảnh class c)

  Lớp có ít ảnh nhận trọng số lớn hơn. Ví dụ bánh xèo có ít ảnh thì dự đoán sai bánh xèo bị phạt
  mạnh hơn.

  Cách nói:

  > “Để xử lý class imbalance, project sử dụng inverse-frequency class weighting trong
  > CrossEntropyLoss.”

  Đây là cost-sensitive learning, không phải oversampling.

  ———

  ### 12. AdamW Optimizer

  Vị trí: ml/training/train.py:519

  AdamW tự điều chỉnh learning rate theo từng tham số và tách weight decay khỏi gradient update.

  Cách nói:

  > “Mô hình được tối ưu bằng AdamW, phù hợp với quá trình fine-tune pretrained backbone và có
  > decoupled weight decay.”

  ———

  ### 13. Cosine Annealing Learning-rate Scheduler

  Vị trí: ml/training/train.py:523

  Learning rate giảm theo đường cosine:

  - Đầu training: bước cập nhật lớn.
  - Cuối training: bước nhỏ hơn để model hội tụ ổn định.

  Cách nói:

  > “Project sử dụng CosineAnnealingLR để giảm learning rate theo cosine schedule trong quá trình
  > fine-tuning.”

  Nó khác hoàn toàn với cosine similarity.

  ———

  ### 14. Data Augmentation

  Vị trí: ml/training/dataset.py:108

  Project áp dụng:

  - Random resized crop
  - Horizontal flip
  - Vertical flip
  - Rotation
  - Affine transformation
  - Color jitter
  - Perspective transformation
  - Random erasing

  Cách nói:

  > “Training pipeline sử dụng stochastic data augmentation để tăng độ đa dạng và giảm
  > overfitting.”

  Đây là nhóm kỹ thuật, không phải một thuật toán duy nhất.

  ———

  ### 15. Confidence Calibration và ECE

  Vị trí: ml/training/train.py:301

  Project tính Expected Calibration Error – ECE bằng cách:

  1. Chia confidence thành 10 bins.
  2. Tính confidence trung bình và accuracy thực tế trong mỗi bin.
  3. Đo khoảng cách giữa độ tự tin và độ chính xác.
  4. Chọn serving threshold đạt target accuracy với coverage tốt nhất.

  Cách nói:

  > “Project đánh giá calibration bằng ECE và tune confidence threshold theo selective accuracy–
  > coverage trade-off.”

  ———

  ### 16. Grid Search cho cascade threshold

  Vị trí: ml/evaluation/tune_cascade.py:125

  Project thử toàn bộ cặp:

  t1 = ngưỡng cosine top-1
  t2 = ngưỡng margin top-1 − top-2

  Sau đó tính precision và coverage cho từng cặp.

  Cách nói:

  > “Hai threshold của recognition cascade được tune bằng exhaustive grid search trên validation
  > set.”

  ———

  ### 17. Pareto Frontier

  Vị trí: ml/evaluation/tune_cascade.py:138

  Dùng để chọn các cấu hình không bị cấu hình khác vượt đồng thời về:

  - Precision
  - Coverage

  Cách nói:

  > “Sau grid search, project dùng Pareto frontier để phân tích trade-off giữa precision và
  > coverage.”

  ———

  ## C. Tìm kiếm văn bản và gợi ý món

  ### 18. Transformer Text Embedding — Qwen3 Embedding

  Vị trí: backend/services/embeddings.py:20

  Qwen3-Embedding chuyển tên món/nguyên liệu thành vector 1024 chiều.

  Cách nói:

  > “Project sử dụng dense semantic retrieval: Qwen3-Embedding mã hóa query và catalog vào cùng
  > không gian vector.”

  Ví dụ "suon" và "sườn" có thể gần nhau về vector dù tìm chuỗi trực tiếp thất bại.

  ———

  ### 19. Exact/Substring Retrieval bằng normalized ILIKE

  Vị trí: backend/services/dishes.py:299

  Luồng:

  1. vn_norm() chuyển về chữ thường và bỏ dấu.
  2. Exact match được ưu tiên.
  3. Sau đó tìm substring bằng ILIKE.
  4. Nếu vẫn không có thì mới semantic search.

  Cách gọi đúng:

  > “Đây là lexical retrieval dựa trên accent normalization và case-insensitive substring
  > matching.”

  Không nên gọi phần này là fuzzy matching, vì nó không tính edit distance.

  ———

  ### 20. Rule-based Re-ranking / Lexical Guard

  Vị trí: backend/services/dishes.py:193

  Sau khi Qdrant trả semantic candidates, project không tin ngay cosine score. Nó kiểm tra:

  - Có cùng họ món hay không.
  - Có đủ token chung không.
  - Ứng viên thêm bao nhiêu token so với query.
  - UUID có tồn tại trong PostgreSQL không.

  Sau đó ưu tiên ứng viên có ít token dư nhất.

  Cách nói:

  > “Project sử dụng hybrid retrieval gồm lexical search, dense vector retrieval và rule-based re-
  > ranking để giảm semantic false positive.”

  Đây là cách gọi rất tốt khi phỏng vấn.

  ———

  ### 21. Weighted Scoring/Heuristic Ranking cho gợi ý món

  Vị trí: backend/services/suggestions.py:160

  Công thức gần đúng:

  score =
      0.5 × macro_fit
    + 0.5 × calorie_fit
    + preference_bonus

  Trước đó món không phù hợp calo, dị ứng hoặc đã ăn sẽ bị loại.

  Cách nói:

  > “Hệ thống gợi ý sử dụng constraint filtering kết hợp weighted heuristic scoring theo calorie
  > fit, macro fit và sở thích.”

  Nó chưa phải collaborative filtering, content-based recommender được huấn luyện, hay deep
  recommendation model.

  ———

  ## D. Tiền xử lý và đánh giá dữ liệu

  ### 22. Perceptual Hash – pHash

  Vị trí: scripts/download_datasets.py:100

  pHash tạo hash dựa trên cấu trúc thị giác của ảnh. Hai ảnh resize hoặc nén khác nhau vẫn có hash
  gần nhau.

  Cách nói:

  > “Project dùng perceptual hashing để phát hiện ảnh trùng hoặc gần trùng trong dataset.”

  ———

  ### 23. Hamming Distance

  Cũng trong scripts/download_datasets.py:100.

  Project tính khoảng cách giữa hai pHash:

  Hamming distance ≤ 4 → xem là ảnh trùng

  Khi chống data leakage ở test split, ngưỡng chặt riêng được đặt là ≤ 6.

  Cách nói:

  > “Khoảng cách Hamming giữa perceptual hashes được dùng để deduplicate ảnh và ngăn near-duplicate
  > leakage giữa train/validation/test.”

  ———

  ### 24. Confusion Matrix và các classification metrics

  Project tính:

  - Accuracy
  - Precision
  - Recall
  - F1-score
  - Macro precision/recall/F1
  - Per-class accuracy
  - Confusion matrix

  Cách nói:

  > “Mô hình được đánh giá bằng macro-F1 và per-class metrics bên cạnh accuracy để tránh lớp đa số
  > che giấu hiệu năng lớp thiểu số.”

  ———

  ## Câu tổng hợp tốt nhất khi trình bày project

  > “FoodAI sử dụng EfficientNet-B0 với transfer learning cho image classification, SigLIP 2 cho
  > image embedding, k-NN/ANN retrieval trên Qdrant với cosine similarity, và Qwen3 Embedding cho
  > semantic text retrieval. Training sử dụng weighted cross-entropy, AdamW, cosine annealing và
  > data augmentation. Pipeline còn có confidence calibration, top-1/top-2 margin, rule-based re-
  > ranking, U²-Net segmentation, cùng pHash và Hamming distance để chống dữ liệu ảnh trùng.”

  Đồng thời cần nói rõ project chưa sử dụng SVM, K-Means, Random Forest, linear regression,
  collaborative filtering hay BM25.

─ Worked for 1m 37s ───────────────────────────────────────────────────────────────────────────────


› cho tôi list câu hỏi từ lớn tới nhỏ đi từ khái niệm ai ,machine learning rồi dần câu trước là
  nền tảng cho những câu sau rồi đi dần vào project. Còn cả be và dev opp để xử lí bài toán nhiều
  người dùng sau này nữa


• Dưới đây là bộ câu hỏi theo thứ tự từ nền tảng đến chuyên sâu. Mỗi nhóm là tiền đề cho nhóm tiếp
  theo, cuối cùng đi vào FoodAI, backend và DevOps để phục vụ nhiều người dùng.

  ## Phần 1 — AI, Machine Learning và Deep Learning

  1. Trí tuệ nhân tạo — AI là gì?
  2. Một hệ thống có nhiều if/else có được gọi là AI không?
  3. AI, Machine Learning và Deep Learning khác nhau thế nào?
  4. Generative AI khác Predictive AI thế nào?
  5. Computer Vision, NLP và Speech AI giải quyết những bài toán gì?
  6. Machine Learning học điều gì từ dữ liệu?
  7. Feature, label và sample là gì?
  8. Training và inference khác nhau thế nào?
  9. Model, algorithm và learned parameters khác nhau thế nào?
  10. Supervised learning là gì?
  11. Unsupervised learning là gì?
  12. Semi-supervised và self-supervised learning là gì?
  13. Reinforcement learning là gì?
  14. Classification khác regression thế nào?
  15. Binary classification và multi-class classification khác nhau ra sao?
  16. Clustering khác classification như thế nào?
  17. Recommendation và information retrieval là bài toán gì?
  18. Một bài toán thực tế nên được chuyển thành bài toán ML như thế nào?
  19. Khi nào không nên dùng Machine Learning?
  20. Làm sao xác định AI thực sự tạo ra giá trị cho sản phẩm?

  ## Phần 2 — Dữ liệu và biểu diễn dữ liệu

  21. Dataset là gì?
  22. Một dataset tốt cần những đặc điểm nào?
  23. Structured data và unstructured data khác nhau thế nào?
  24. Training, validation và test set dùng để làm gì?
  25. Tại sao không được dùng test set để điều chỉnh model?
  26. Data leakage là gì?
  27. Duplicate và near-duplicate image gây data leakage thế nào?
  28. Ground truth là gì?
  29. Label noise là gì?
  30. Class imbalance là gì?
  31. Một lớp có nhiều ảnh hơn các lớp khác gây hậu quả gì?
  32. Sampling và class weighting khác nhau thế nào?
  33. Data preprocessing gồm những công việc gì?
  34. Normalization và standardization khác nhau thế nào?
  35. Data augmentation là gì?
  36. Tại sao augmentation chỉ nên áp dụng ngẫu nhiên cho tập train?
  37. Horizontal flip, rotation và color jitter mô phỏng điều gì?
  38. Khi nào augmentation có thể làm sai nhãn?
  39. pHash là gì?
  40. Hamming distance là gì?
  41. FoodAI dùng pHash và Hamming distance để làm gì?
  42. Làm sao chia train/validation/test mà không để ảnh gần trùng lọt qua?
  43. Dataset shift và concept drift là gì?
  44. Làm sao phát hiện dữ liệu production khác dữ liệu train?

  ## Phần 3 — Toán nền tảng cho Machine Learning

  45. Scalar, vector, matrix và tensor là gì?
  46. Một bức ảnh được biểu diễn thành tensor như thế nào?
  47. Vector embedding là gì?
  48. Dimension của embedding có ý nghĩa gì?
  49. Dot product là gì?
  50. Norm của vector là gì?
  51. L1 norm và L2 norm khác nhau thế nào?
  52. L2 normalization dùng để làm gì?
  53. Euclidean distance là gì?
  54. Manhattan distance là gì?
  55. Cosine similarity là gì?
  56. Cosine similarity khác Euclidean distance thế nào?
  57. Khi nào nên dùng cosine similarity?
  58. Tại sao embedding thường được so sánh bằng cosine?
  59. Xác suất và confidence có giống nhau không?
  60. Logit là gì?
  61. Softmax hoạt động như thế nào?
  62. Tại sao softmax phù hợp với multi-class classification?
  63. Argmax và Top-k là gì?
  64. Loss function dùng để làm gì?
  65. Gradient là gì?
  66. Gradient descent cập nhật model như thế nào?
  67. Learning rate ảnh hưởng đến training ra sao?
  68. Epoch, batch và iteration khác nhau thế nào?
  69. Backpropagation là gì?
  70. Weight decay và regularization dùng để làm gì?

  ## Phần 4 — Machine Learning cổ điển và tìm kiếm hàng xóm

  71. Linear regression giải quyết bài toán gì?
  72. Logistic regression là regression hay classification?
  73. Decision Tree hoạt động thế nào?
  74. Random Forest cải thiện Decision Tree ra sao?
  75. SVM tìm decision boundary như thế nào?
  76. K-Means clustering hoạt động thế nào?
  77. K-Means và k-NN khác nhau ra sao?
  78. k-Nearest Neighbors — k-NN là gì?
  79. k trong k-NN có ý nghĩa gì?
  80. k quá nhỏ hoặc quá lớn gây vấn đề gì?
  81. k-NN classification và k-NN retrieval khác nhau thế nào?
  82. Exact Nearest Neighbor Search hoạt động thế nào?
  83. Tại sao tìm tuần tự trên hàng triệu vector bị chậm?
  84. Approximate Nearest Neighbor — ANN là gì?
  85. ANN đánh đổi accuracy và latency như thế nào?
  86. HNSW là gì?
  87. HNSW biểu diễn vector thành graph như thế nào?
  88. Qdrant dùng ANN/HNSW để giải quyết vấn đề gì?
  89. FoodAI có tự cài thuật toán k-NN hoặc HNSW không?
  90. limit=30 trong tìm kiếm ảnh có liên quan đến k thế nào?

  ## Phần 5 — Deep Learning và Computer Vision

  91. Neural network là gì?
  92. Input layer, hidden layer và output layer làm gì?
  93. Activation function dùng để làm gì?
  94. ReLU có vai trò gì?
  95. Vanishing gradient là gì?
  96. CNN là gì?
  97. Kernel/filter trong CNN học điều gì?
  98. Convolution operation hoạt động thế nào?
  99. Stride và padding ảnh hưởng đến feature map ra sao?
  100. Pooling dùng để làm gì?
  101. Receptive field là gì?
  102. CNN học cạnh, texture và hình dạng theo các tầng thế nào?
  103. Image classification, object detection và segmentation khác nhau ra sao?
  104. Backbone và classification head là gì?
  105. ResNet giải quyết vanishing gradient như thế nào?
  106. EfficientNet là gì?
  107. EfficientNet compound scaling là gì?
  108. EfficientNet-B0 khác ResNet50 như thế nào?
  109. Tại sao FoodAI hiện dùng EfficientNet-B0?
  110. Pretrained model là gì?
  111. Transfer learning là gì?
  112. Feature extraction và fine-tuning khác nhau thế nào?
  113. Khi thay số lượng món, tại sao phải thay classification head?
  114. Dropout dùng để làm gì?
  115. Overfitting và underfitting là gì?
  116. Làm sao nhận biết model đang overfit?
  117. Cross-entropy loss hoạt động thế nào?
  118. Weighted cross-entropy xử lý class imbalance thế nào?
  119. Adam khác SGD như thế nào?
  120. AdamW khác Adam ở điểm nào?
  121. Cosine annealing scheduler là gì?
  122. Cosine annealing có liên quan cosine similarity không?
  123. Confusion matrix cho biết điều gì?
  124. Accuracy có thể gây hiểu nhầm thế nào?
  125. Precision, recall và F1-score khác nhau ra sao?
  126. Micro-F1 và macro-F1 khác nhau thế nào?
  127. Tại sao FoodAI nên chú ý macro-F1 và per-class recall?
  128. Confidence calibration là gì?
  129. Expected Calibration Error — ECE là gì?
  130. Selective prediction là gì?
  131. Precision–coverage trade-off là gì?
  132. FoodAI chọn confidence threshold bằng cách nào?

  ## Phần 6 — Embedding, Transformer và Vector Search

  133. Representation learning là gì?
  134. Embedding model học không gian vector như thế nào?
  135. Text embedding và image embedding khác nhau thế nào?
  136. Semantic similarity khác lexical similarity thế nào?
  137. Tại sao "sườn" và "suon" có thể có embedding gần nhau?
  138. Dense retrieval là gì?
  139. Sparse retrieval là gì?
  140. BM25 hoạt động theo nguyên tắc nào?
  141. Dense retrieval và BM25 có ưu, nhược điểm gì?
  142. Hybrid retrieval là gì?
  143. Bi-encoder và cross-encoder khác nhau thế nào?
  144. Qwen3-Embedding được dùng ở đâu trong FoodAI?
  145. Tại sao query và catalog phải dùng cùng embedding model?
  146. Điều gì xảy ra nếu đổi embedding model nhưng không reindex Qdrant?
  147. Vector dimension 1024 có ý nghĩa gì?
  148. SigLIP 2 là gì?
  149. Contrastive learning là gì?
  150. SigLIP 2 biến ảnh thành embedding 768 chiều như thế nào?
  151. Tại sao FoodAI L2-normalize image embedding?
  152. Vector database là gì?
  153. Qdrant khác PostgreSQL thế nào?
  154. Collection, point, vector và payload trong Qdrant là gì?
  155. Cosine score trong Qdrant được diễn giải thế nào?
  156. Similarity threshold 0.75 có phải ngưỡng đúng cho mọi model không?
  157. Filter payload được áp dụng trong vector search như thế nào?
  158. Tại sao Qdrant chỉ nên là derived index?
  159. Tại sao kết quả Qdrant phải resolve lại qua UUID PostgreSQL?
  160. Index drift là gì?
  161. Missing point và orphaned point là gì?
  162. Khi Qdrant mất dữ liệu, FoodAI có thể phục hồi thế nào?

  ## Phần 7 — Pipeline nhận diện ảnh của FoodAI

  163. Bài toán nhận diện món Việt của FoodAI được định nghĩa như thế nào?
  164. Input và output của endpoint /analyze là gì?
  165. Local CV, image retrieval và cloud Vision khác nhau thế nào?
  166. Tại sao không gọi cloud Vision cho mọi request?
  167. Recognition cascade là gì?
  168. Ảnh upload đi qua những bước nào?
  169. EfficientNet-B0 tạo kết quả local như thế nào?
  170. Khi nào FoodAI tin kết quả local CV?
  171. Khi nào local CV phải fallback?
  172. SigLIP tạo image embedding như thế nào?
  173. Qdrant tìm các ảnh tham chiếu gần nhất thế nào?
  174. Các image hits được gom theo món như thế nào?
  175. best_score và votes có ý nghĩa gì?
  176. Top-1 score là gì?
  177. Top-1/Top-2 margin là gì?
  178. Tại sao chỉ kiểm tra Top-1 score là chưa đủ?
  179. Điều kiện nào khiến image k-NN được phép trả kết quả trực tiếp?
  180. Khi không đủ tự tin, candidate names được dùng thế nào?
  181. Vision model nhận ảnh và candidates như thế nào?
  182. Tại sao cần lexical guard sau semantic matching?
  183. Vì sao "Nem nướng" không nên tự động biến thành "Bún nem nướng"?
  184. Cascade giúp giảm latency và chi phí cloud thế nào?
  185. Sidecar SigLIP hỏng thì hệ thống fallback thế nào?
  186. Qdrant hỏng thì /analyze có nên hỏng theo không?
  187. Làm sao tune image score threshold và margin threshold?
  188. Grid search được dùng thế nào?
  189. Pareto frontier giúp chọn threshold ra sao?
  190. Làm sao đánh giá end-to-end accuracy của toàn cascade?

  ## Phần 8 — Vision–Language Model và Generative AI

  191. Large Language Model — LLM là gì?
  192. Transformer là gì?
  193. Attention giải quyết vấn đề gì?
  194. Token là gì?
  195. Context window là gì?
  196. Vision–Language Model khác image classifier thế nào?
  197. Qwen Vision có thể trả thêm thông tin gì ngoài tên món?
  198. Prompt engineering là gì?
  199. Structured output bằng JSON có lợi gì?
  200. Hallucination là gì?
  201. Vì sao Vision có thể đoán sai nguyên liệu hoặc khối lượng?
  202. Temperature ảnh hưởng output như thế nào?
  203. Tại sao cần validate JSON từ LLM?
  204. Nếu LLM trả Markdown hoặc thinking tags thì xử lý thế nào?
  205. LLM local qua llama.cpp khác cloud API thế nào?
  206. Quantization Q4/Q8 là gì?
  207. Quantization đánh đổi bộ nhớ, tốc độ và chất lượng như thế nào?
  208. Embedding model và generative LLM khác nhau thế nào?
  209. RAG là gì?
  210. FoodAI hiện có phần nào mang tính retrieval-augmented?
  211. LLM-as-a-judge là gì?
  212. Tại sao không nên dùng duy nhất LLM-as-a-judge để đánh giá?
  213. RAGAS Context Recall và Context Precision đo điều gì?

  ## Phần 9 — Dinh dưỡng và hệ thống gợi ý

  214. Dinh dưỡng theo per gram, per 100g và per serving khác nhau thế nào?
  215. Tại sao không được biến tổng dinh dưỡng vnmeal thành per-100g tùy ý?
  216. FoodAI tính dinh dưỡng nguyên liệu như thế nào?
  217. Conversion rate được dùng để làm gì?
  218. Tại sao phải tái sử dụng calculate_ingredient_nutrition()?
  219. Floating-point error có thể ảnh hưởng phép tính thế nào?
  220. Rounding nên thực hiện ở business layer hay presentation layer?
  221. Content-based recommendation là gì?
  222. Collaborative filtering là gì?
  223. FoodAI hiện đã dùng collaborative filtering chưa?
  224. FoodAI hiện xếp hạng món bằng cách nào?
  225. Constraint filtering là gì?
  226. Calorie fit được tính thế nào?
  227. Macro fit được tính thế nào?
  228. Weighted heuristic scoring là gì?
  229. Làm sao cộng preference bonus mà không phá vỡ điểm chính?
  230. Tại sao lọc dị ứng bằng tên món không đủ an toàn?
  231. Khi nào nên chuyển heuristic recommender sang learning-to-rank?
  232. Cần thu thập dữ liệu gì để xây recommender cá nhân hóa?
  233. Usage count, click, save và consume event có thể dùng thế nào?
  234. Offline recommendation metrics gồm những gì?
  235. A/B test recommender trong production như thế nào?

  ## Phần 10 — Thiết kế backend căn bản

  236. Client–server architecture là gì?
  237. HTTP request và response gồm những phần nào?
  238. REST API là gì?
  239. Resource-oriented API design là gì?
  240. GET, POST, PUT, PATCH, DELETE khác nhau thế nào?
  241. Idempotency là gì?
  242. HTTP status 200, 201, 400, 401, 404, 409, 422, 429 và 500 dùng khi nào?
  243. JSON serialization là gì?
  244. Schema validation dùng để làm gì?
  245. Pydantic đóng vai trò gì trong FastAPI?
  246. Dependency Injection là gì?
  247. Depends(get_session) hoạt động thế nào?
  248. Router, service và repository/data-access layer khác nhau ra sao?
  249. Tại sao không nên viết toàn bộ business logic trong endpoint?
  250. Synchronous và asynchronous processing khác nhau thế nào?
  251. async/await giúp gì cho API có nhiều I/O?
  252. Async có làm phép tính CPU chạy nhanh hơn không?
  253. Event loop là gì?
  254. Blocking call có thể làm nghẽn FastAPI thế nào?
  255. Tại sao project đưa Qdrant client đồng bộ vào asyncio.to_thread()?
  256. Khi nào nên dùng thread pool?
  257. Khi nào nên dùng process pool?
  258. Khi nào cần một worker queue riêng?

  ## Phần 11 — PostgreSQL và quản lý dữ liệu

  259. Relational database là gì?
  260. Table, row, column và schema là gì?
  261. Primary key và foreign key dùng để làm gì?
  262. UUID khác auto-increment ID thế nào?
  263. Unique constraint bảo vệ điều gì?
  264. Tại sao contribute trùng dish_name trả HTTP 409?
  265. Index trong PostgreSQL hoạt động thế nào?
  266. Index giúp đọc nhanh nhưng gây chi phí ghi ra sao?
  267. B-tree index phù hợp với loại truy vấn nào?
  268. LIKE và ILIKE khác nhau thế nào?
  269. vn_norm() giải quyết tìm kiếm tiếng Việt ra sao?
  270. Exact match, prefix match và substring match có hiệu năng khác nhau thế nào?
  271. JOIN là gì?
  272. INNER JOIN và LEFT JOIN khác nhau thế nào?
  273. N+1 query problem là gì?
  274. Transaction là gì?
  275. ACID là gì?
  276. Commit và rollback được dùng khi nào?
  277. Transaction isolation level là gì?
  278. Race condition khi hai người cùng contribute một món xảy ra thế nào?
  279. Tại sao phải dựa vào UNIQUE constraint thay vì chỉ SELECT trước?
  280. Connection pool là gì?
  281. Nếu pool có 20 connection nhưng có 1.000 request thì chuyện gì xảy ra?
  282. Làm sao chọn pool size?
  283. Slow query là gì?
  284. Dùng EXPLAIN ANALYZE để làm gì?
  285. Alembic migration là gì?
  286. Tại sao migration phải có khả năng chạy an toàn trên production?
  287. Zero-downtime database migration là gì?
  288. Backup và point-in-time recovery là gì?
  289. Tại sao PostgreSQL là source of truth còn Qdrant không phải?

  ## Phần 12 — API FoodAI và 2-tier dish lookup

  290. Kiến trúc 2-tier dish lookup giải quyết vấn đề gì?
  291. Tier 1 và Tier 2 là gì?
  292. /dishes/lookup tìm institute dish trước như thế nào?
  293. Tại sao source=vnmeal được ưu tiên?
  294. Khi nào lookup chuyển sang user recipe?
  295. exists=false có ý nghĩa gì?
  296. /dishes/compute khác /dishes như thế nào?
  297. Preview không lưu dữ liệu có lợi gì?
  298. Contribute món mới cần validate những gì?
  299. Ingredient search chạy exact/ILIKE trước vì sao?
  300. Khi nào mới sử dụng Qdrant semantic fallback?
  301. Hybrid retrieval trong FoodAI gồm những tầng nào?
  302. Tại sao vector score cao chưa chắc là đúng món?
  303. Rule-based semantic guard ngăn false positive thế nào?
  304. Tại sao Qdrant result phải resolve qua PostgreSQL?
  305. Điều gì xảy ra khi Qdrant chứa UUID đã bị xóa khỏi PostgreSQL?
  306. Reindex có ảnh hưởng đến API đang chạy không?
  307. Làm sao thực hiện blue/green reindex cho vector collection?
  308. Trust score và recipe versioning sau này giải quyết vấn đề gì?
  309. Admin verification nên được thiết kế thế nào?
  310. Audit log cần lưu những thay đổi nào?

  ## Phần 13 — Authentication và bảo mật

  311. Authentication và authorization khác nhau thế nào?
  312. Session-based auth và token-based auth khác nhau ra sao?
  313. JWT gồm những phần nào?
  314. Access token và refresh token khác nhau thế nào?
  315. Password phải được hash như thế nào?
  316. Argon2 chống brute force tốt hơn hash nhanh ở điểm nào?
  317. Tại sao không được lưu plaintext password?
  318. SQL injection là gì?
  319. ORM có tự động loại bỏ mọi nguy cơ SQL injection không?
  320. Input validation ngăn được những lỗi nào?
  321. File upload có những rủi ro bảo mật nào?
  322. Làm sao kiểm tra file thật sự là ảnh?
  323. Giới hạn kích thước ảnh để làm gì?
  324. Prompt injection qua nội dung người dùng có thể xảy ra thế nào?
  325. Secret và API key nên được quản lý ở đâu?
  326. Tại sao không commit .env?
  327. CORS là gì?
  328. CSRF là gì?
  329. XSS là gì?
  330. Rate limiting bảo vệ hệ thống thế nào?
  331. Per-user và per-IP rate limit khác nhau thế nào?
  332. API /analyze nên có quota riêng vì sao?
  333. Audit log bảo mật nên chứa gì và không nên chứa gì?
  334. PII là gì?
  335. Ảnh đồ ăn có thể vô tình chứa dữ liệu cá nhân nào?
  336. Retention policy cho ảnh upload nên được thiết kế ra sao?

  ## Phần 14 — Xử lý nhiều người dùng đồng thời

  337. Concurrency và parallelism khác nhau thế nào?
  338. Throughput và latency khác nhau thế nào?
  339. P50, P95 và P99 latency là gì?
  340. Một request /analyze tiêu thụ những tài nguyên nào?
  341. Bottleneck có thể nằm ở API, PostgreSQL, Qdrant hay model server thế nào?
  342. FastAPI worker là gì?
  343. Tăng số worker có luôn tăng throughput không?
  344. Nếu mỗi worker tự load một model lớn thì chuyện gì xảy ra?
  345. CPU-bound và I/O-bound workload khác nhau thế nào?
  346. GPU/MPS inference có thể xử lý song song bao nhiêu request?
  347. Tại sao model server cần giới hạn concurrency?
  348. Semaphore/concurrency cap hoạt động thế nào?
  349. Backpressure là gì?
  350. Khi downstream quá tải, API nên làm gì?
  351. Timeout nên được đặt ở những tầng nào?
  352. Retry có thể gây retry storm thế nào?
  353. Exponential backoff và jitter là gì?
  354. Circuit breaker là gì?
  355. FoodAI dùng circuit breaker cho sidecar thế nào?
  356. Failure threshold và recovery time có ý nghĩa gì?
  357. Bulkhead pattern là gì?
  358. Làm sao cách ly embedding, Vision và segmentation để một dịch vụ hỏng không kéo sập toàn hệ
     thống?

  359. Graceful degradation là gì?
  360. FoodAI fallback khi SigLIP hoặc Qdrant hỏng như thế nào?
  361. Load shedding là gì?
  362. Khi hệ thống quá tải, nên từ chối request nào trước?
  363. Queue giúp hấp thụ traffic spike ra sao?
  364. Khi nào /analyze nên chuyển thành asynchronous job?
  365. Polling, WebSocket và Server-Sent Events khác nhau thế nào?
  366. Celery, RQ, Dramatiq hoặc Kafka có thể được dùng ở đâu?
  367. Idempotency key giúp tránh xử lý job trùng thế nào?
  368. At-most-once, at-least-once và exactly-once khác nhau ra sao?
  369. Làm sao chống người dùng upload cùng ảnh nhiều lần?
  370. Cache kết quả bằng hash ảnh có hợp lý không?

  ## Phần 15 — Caching và tối ưu hiệu năng

  371. Cache là gì?
  372. Cache-aside pattern hoạt động thế nào?
  373. Những dữ liệu nào của FoodAI có thể cache?
  374. Có nên cache kết quả Vision theo hash ảnh không?
  375. Có nên cache text embedding theo normalized query không?
  376. Redis khác in-memory cache trong từng worker thế nào?
  377. Cache key nên được thiết kế ra sao?
  378. TTL là gì?
  379. Cache invalidation khó ở điểm nào?
  380. Khi catalog thay đổi, cache lookup phải được xóa thế nào?
  381. Cache stampede là gì?
  382. Request coalescing giúp chống cache stampede thế nào?
  383. CDN dùng được cho loại tài nguyên nào?
  384. Object storage khác database thế nào?
  385. Ảnh upload nên lưu local disk hay S3-compatible storage?
  386. Presigned URL là gì?
  387. Compression và resize ảnh trước inference giúp gì?
  388. Dynamic batching cho embedding hoạt động thế nào?
  389. Batch inference cải thiện throughput nhưng tăng latency thế nào?
  390. Làm sao benchmark số batch phù hợp?

  ## Phần 16 — Kiến trúc hệ thống khi mở rộng

  391. Monolith, modular monolith và microservices khác nhau thế nào?
  392. FoodAI hiện phù hợp với kiến trúc nào?
  393. Khi nào không nên tách microservices?
  394. Thành phần nào có thể tách trước khi traffic tăng?
  395. API service, inference service và background worker nên giao tiếp thế nào?
  396. Stateless API là gì?
  397. Vì sao stateless service dễ scale ngang?
  398. Vertical scaling và horizontal scaling khác nhau thế nào?
  399. Load balancer phân phối request như thế nào?
  400. Round-robin và least-connections khác nhau ra sao?
  401. Sticky session là gì và khi nào cần?
  402. Service discovery là gì?
  403. API gateway có vai trò gì?
  404. Reverse proxy như Nginx hoặc Traefik làm gì?
  405. Health check readiness và liveness khác nhau thế nào?
  406. Nếu embedding model chưa load xong, readiness nên trả gì?
  407. Autoscaling nên dựa vào CPU, queue depth hay latency?
  408. Database có scale ngang giống API được không?
  409. Read replica giúp gì?
  410. Read-after-write consistency là gì?
  411. Sharding là gì?
  412. Khi nào PostgreSQL của FoodAI thực sự cần sharding?
  413. CAP theorem nói về điều gì?
  414. Strong consistency và eventual consistency khác nhau thế nào?
  415. Vì sao PostgreSQL–Qdrant chấp nhận eventual consistency?
  416. Outbox pattern là gì?
  417. Làm sao đảm bảo PostgreSQL commit thành công rồi Qdrant được cập nhật?
  418. Nếu upsert Qdrant thất bại sau DB commit thì xử lý thế nào?
  419. Reconciliation job sửa index drift ra sao?
  420. Event-driven architecture có thể áp dụng vào FoodAI như thế nào?

  ## Phần 17 — Docker và môi trường triển khai

  421. Container khác virtual machine thế nào?
  422. Docker image và container khác nhau ra sao?
  423. Dockerfile gồm những layer nào?
  424. Tại sao Docker layer cache ảnh hưởng build speed?
  425. Multi-stage build là gì?
  426. Làm sao giảm kích thước image?
  427. Tại sao container không nên chạy bằng root?
  428. Docker Compose giải quyết vấn đề gì?
  429. FoodAI hiện chạy những service nào?
  430. Tại sao embedding server không nằm trong Compose hiện tại?
  431. Volume dùng để làm gì?
  432. Nếu xóa PostgreSQL container nhưng giữ volume thì dữ liệu ra sao?
  433. Port mapping 5432:5432 có ý nghĩa gì?
  434. Container gọi nhau bằng localhost có được không?
  435. Docker network và service name hoạt động thế nào?
  436. Environment variable được truyền vào container ra sao?
  437. Health check trong Compose dùng để làm gì?
  438. depends_on có đảm bảo database sẵn sàng nhận query không?
  439. Graceful shutdown trong container là gì?
  440. SIGTERM nên được xử lý thế nào?

  ## Phần 18 — CI/CD và DevOps

  441. DevOps là gì?
  442. CI và CD khác nhau thế nào?
  443. Một pipeline CI của FoodAI nên có những bước nào?
  444. Lint, type check và unit test khác nhau thế nào?
  445. Test pyramid là gì?
  446. Unit, integration và end-to-end test dùng khi nào?
  447. Làm sao test PostgreSQL và Qdrant trong CI?
  448. Có nên gọi cloud Vision thật trong test không?
  449. Mock, stub và fake khác nhau thế nào?
  450. Coverage 80% có đảm bảo phần mềm không có bug không?
  451. Migration test nên kiểm tra điều gì?
  452. Model artifact có nên lưu trong Git không?
  453. Model registry là gì?
  454. Model version và code version nên liên kết thế nào?
  455. Dataset versioning là gì?
  456. DVC hoặc object storage có thể giúp gì?
  457. Reproducible training là gì?
  458. Random seed có đảm bảo tái lập tuyệt đối không?
  459. Model promotion từ staging sang production diễn ra thế nào?
  460. Blue–green deployment là gì?
  461. Canary deployment là gì?
  462. Rolling deployment là gì?
  463. Database migration nên chạy ở thời điểm nào trong deployment?
  464. Làm sao rollback code khi schema đã thay đổi?
  465. Feature flag dùng để làm gì?
  466. Làm sao bật image cascade cho một phần người dùng?
  467. Infrastructure as Code là gì?
  468. Terraform giải quyết vấn đề gì?
  469. GitHub Actions có thể triển khai FoodAI như thế nào?
  470. Secret trong CI/CD nên được quản lý ở đâu?
  471. Software supply-chain security là gì?
  472. Dependency scanning và container scanning dùng để làm gì?

  ## Phần 19 — Kubernetes khi hệ thống lớn hơn

  473. Kubernetes giải quyết vấn đề gì?
  474. Pod, Deployment và Service khác nhau thế nào?
  475. ConfigMap và Secret khác nhau thế nào?
  476. Ingress là gì?
  477. ReplicaSet duy trì số lượng pod như thế nào?
  478. Horizontal Pod Autoscaler hoạt động ra sao?
  479. CPU request/limit khác nhau thế nào?
  480. Nếu đặt memory limit quá thấp thì chuyện gì xảy ra?
  481. Liveness probe cấu hình sai có thể tạo restart loop thế nào?
  482. Readiness probe bảo vệ traffic khi model chưa load ra sao?
  483. StatefulSet phù hợp với service nào?
  484. Có nên tự vận hành PostgreSQL trong Kubernetes không?
  485. PersistentVolume dùng để làm gì?
  486. Node có GPU nên được đánh dấu và schedule thế nào?
  487. Model server có nên autoscale giống API không?
  488. Cold start khi load model ảnh hưởng autoscaling thế nào?
  489. Pod disruption budget là gì?
  490. Kubernetes có cần thiết cho FoodAI ở giai đoạn hiện tại không?

  Câu trả lời hợp lý thường là:

  > “Chưa cần ngay. Docker Compose hoặc một nền tảng managed đơn giản phù hợp hơn cho giai đoạn
  > đầu. Kubernetes chỉ đáng dùng khi số service, traffic và yêu cầu availability đủ lớn để bù chi
  > phí vận hành.”

  ## Phần 20 — Observability và vận hành production

  491. Monitoring, logging và tracing khác nhau thế nào?
  492. Metric, log và trace được gọi chung là gì?
  493. Structured logging là gì?
  494. Correlation ID/request ID dùng để làm gì?
  495. Một request /analyze nên được trace qua những service nào?
  496. OpenTelemetry giải quyết vấn đề gì?
  497. Prometheus thu thập metric như thế nào?
  498. Grafana dùng để làm gì?
  499. FoodAI nên theo dõi những metric API nào?
  500. FoodAI nên theo dõi những metric model nào?
  501. Request rate, error rate và duration tạo thành RED metrics thế nào?
  502. Saturation cho database và model server được đo ra sao?
  503. SLI, SLO và SLA khác nhau thế nào?
  504. Error budget là gì?
  505. Alert nên dựa trên triệu chứng hay nguyên nhân?
  506. Tại sao không nên alert cho mọi lỗi đơn lẻ?
  507. Log có được chứa password, token hoặc ảnh base64 không?
  508. Slow query log giúp gì?
  509. Qdrant search latency nên được đo riêng thế nào?
  510. Làm sao đo tỷ lệ fallback từ local CV sang cloud Vision?
  511. Làm sao theo dõi chi phí Vision trên mỗi người dùng?
  512. Model drift nên được monitoring thế nào?
  513. Tỷ lệ user correction phản ánh chất lượng model ra sao?
  514. Dashboard production của FoodAI nên có những biểu đồ nào?
  515. Incident response gồm các bước nào?
  516. Runbook là gì?
  517. Postmortem không đổ lỗi nên ghi những gì?

  ## Phần 21 — Thiết kế FoodAI cho nhiều người dùng

  518. Một request phân tích ảnh đi qua kiến trúc production thế nào?
  519. Thành phần nào nên stateless?
  520. Thành phần nào giữ state?
  521. Ảnh upload nên đi thẳng qua API hay object storage?
  522. Làm sao tránh API giữ file lớn trong RAM quá lâu?
  523. Khi 1.000 người upload ảnh cùng lúc, điểm nghẽn đầu tiên có thể ở đâu?
  524. API nên giới hạn số request đồng thời thế nào?
  525. Model inference nên dùng queue hay xử lý đồng bộ?
  526. Request nhanh và request chậm nên tách queue không?
  527. Làm sao đặt timeout budget cho toàn request?
  528. Nếu Vision mất 20 giây, trải nghiệm UI nên được thiết kế thế nào?
  529. Khi người dùng đóng ứng dụng, job có tiếp tục không?
  530. Làm sao hủy một job không còn cần thiết?
  531. Kết quả phân tích cần lưu snapshot hay tính lại mỗi lần?
  532. Làm sao chống một người dùng chiếm hết tài nguyên?
  533. Quota miễn phí và trả phí nên được áp dụng ở đâu?
  534. Rate limit có cần distributed storage không?
  535. Redis có thể lưu rate-limit counter thế nào?
  536. Làm sao ưu tiên người dùng trả phí?
  537. Fair scheduling là gì?
  538. Một user gửi 100 job có nên chạy trước job của user khác không?
  539. Database schema cần thêm user_id ở những bảng nào?
  540. Làm sao cô lập dữ liệu giữa các người dùng?
  541. Row-level security là gì?
  542. Pagination cần thiết khi meal history lớn thế nào?
  543. Cursor pagination khác offset pagination ra sao?
  544. Retention và xóa tài khoản phải xử lý ảnh, meal log và feedback thế nào?
  545. Backup PostgreSQL nhưng không backup ảnh có đủ không?
  546. Disaster recovery plan cần những gì?
  547. Recovery Point Objective — RPO là gì?
  548. Recovery Time Objective — RTO là gì?
  549. Multi-region deployment có thực sự cần ở giai đoạn đầu không?
  550. Kiến trúc tối thiểu nào đủ phục vụ 100, 1.000 và 100.000 người dùng?

  ## Trình tự học đề xuất

  Không cần học đồng thời cả 550 câu. Có thể đi theo các mốc:

  1. Nền tảng AI: câu 1–90.
  2. Computer Vision: câu 91–132.
  3. Embedding và vector search: câu 133–162.
  4. Pipeline FoodAI: câu 163–235.
  5. Backend và database: câu 236–310.
  6. Security và concurrency: câu 311–390.
  7. System design: câu 391–420.
  8. Docker và DevOps: câu 421–490.
  9. Production operation: câu 491–550.

  Một fresher không cần thuộc lòng tất cả. Mục tiêu tốt hơn là trả lời mỗi câu theo bốn ý:

  1. Định nghĩa: Nó là gì?
  2. Lý do: Nó giải quyết vấn đề gì?
  3. Cách dùng: FoodAI sử dụng nó ở đâu?
  4. Giới hạn: Khi nào nó thất bại hoặc không nên dùng?

  Ví dụ:

  > “Cosine similarity đo độ giống nhau về hướng giữa hai vector. FoodAI dùng nó trong Qdrant để so
  > text embedding và image embedding. Nó phù hợp vì ý nghĩa chủ yếu nằm ở hướng vector. Tuy nhiên
  > score cao không bảo đảm đúng món, nên hệ thống còn dùng threshold, lexical guard và kiểm tra
  > PostgreSQL.”