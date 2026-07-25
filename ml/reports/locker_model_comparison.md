# locker 모델 비교 (leave-facility-out)

| 모델 | CV F1 (macro) | std |
|---|---|---|
| RF(balanced) | 0.460 | 0.081 |
| XGBoost | 0.466 | 0.074 |
| XGBoost+SMOTE **✓** | 0.488 | 0.066 |
| XGBoost+ADASYN | 0.471 | 0.057 |
| XGBoost+BorderSMOTE | 0.462 | 0.041 |

## 테스트셋 성능 (미등장 시설)

```
              precision    recall  f1-score   support

          여유       0.93      0.87      0.90     49205
          보통       0.17      0.27      0.21      3977
          혼잡       0.42      0.55      0.48      3050

    accuracy                           0.81     56232
   macro avg       0.51      0.56      0.53     56232
weighted avg       0.85      0.81      0.83     56232

```