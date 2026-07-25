# library 모델 비교 (leave-facility-out)

| 모델 | CV F1 (macro) | std |
|---|---|---|
| RF(balanced) | 0.431 | 0.033 |
| XGBoost **✓** | 0.444 | 0.044 |
| XGBoost+SMOTE | 0.431 | 0.040 |
| XGBoost+ADASYN | 0.415 | 0.058 |
| XGBoost+BorderSMOTE | 0.409 | 0.056 |

## 테스트셋 성능 (미등장 시설)

```
              precision    recall  f1-score   support

          여유       0.69      0.47      0.56      3740
          보통       0.03      0.04      0.03       971
          혼잡       0.00      0.00      0.00       898

    accuracy                           0.32      5609
   macro avg       0.24      0.17      0.20      5609
weighted avg       0.47      0.32      0.38      5609

```