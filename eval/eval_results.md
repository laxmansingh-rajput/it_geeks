# Evaluation Results (40 Test Queries)

**Summary**: 40/40 queries evaluated against corpus of 4,200 messages. **Recall@3: 77.5%**, **Zero Keyword Overlap Queries: 10 (100% verified)**, **Clarification Triggers: 0**, **Out-of-Domain Rejection Accuracy: 100.0%**.

| ID | Type | Query | Gold Msg | Top-1 Match | @1 | @3 | @5 | Zero Overlap |
|---|---|---|---|---|:---:|:---:|:---:|:---:|
| q01 | Semantic | when did we decide on Manali | `m0952` | `m0946` | ❌ | ✅ | ✅ | No |
| q02 | Semantic | where did we agree to travel | `m0952` | `m0949` | ❌ | ✅ | ✅ | ⭐️ **Yes** |
| q03 | Semantic | when did we decide on the trip destination | `m0952` | `m0942` | ❌ | ✅ | ✅ | ⭐️ **Yes** |
| q04 | Semantic | how much per head was agreed for Manali | `m1150` | `m0947` | ❌ | ❌ | ❌ | ⭐️ **Yes** |
| q05 | Semantic | what total expenditure was confirmed for Old Manali | `m1150` | `m0948` | ❌ | ❌ | ❌ | ⭐️ **Yes** |
| q06 | Semantic | when did we finalize travel dates for the getaway | `m1445` | `m1445` | ✅ | ✅ | ✅ | ⭐️ **Yes** |
| q07 | Semantic | which days are reserved for our holiday | `m1445` | `m1444` | ❌ | ✅ | ✅ | ⭐️ **Yes** |
| q08 | Semantic | what did Amit reply about going to the hills | `m0950` | `m0943` | ❌ | ✅ | ✅ | ⭐️ **Yes** |
| q09 | Semantic | did Amit apply for office leave | `m1442` | `m1442` | ✅ | ✅ | ✅ | ⭐️ **Yes** |
| q10 | Semantic | venue for birthday boy's weekend surprise dinner | `m0521` | `m0516` | ❌ | ✅ | ✅ | ⭐️ **Yes** |
| q11 | Semantic | which cinema hall will we visit | `m2433` | `m2434` | ❌ | ✅ | ✅ | ⭐️ **Yes** |
| q12 | Semantic | what is our team name for the hackathon | `m2943` | `m2939` | ❌ | ✅ | ✅ | No |
| q13 | Semantic | who confirmed the tickets for Select Citywalk IMAX | `m2433` | `m2434` | ❌ | ✅ | ✅ | No |
| q14 | Semantic | cottages in Old Manali mountain view | `m0944` | `m0947` | ❌ | ✅ | ✅ | No |
| q15 | Semantic | Volvo bus booking May 15 to 19 | `m1447` | `m1756` | ❌ | ❌ | ❌ | No |
| q16 | Attributed | what did Priya say about the trip budget | `m1150` | `m1150` | ✅ | ✅ | ✅ | No |
| q17 | Attributed | what did Rohan say about the destination fix | `m0952` | `m0938` | ❌ | ✅ | ✅ | No |
| q18 | Attributed | what did Vikram say about booking the dates | `m1445` | `m1438` | ❌ | ✅ | ✅ | No |
| q19 | Attributed | what did Sara suggest about Old Manali stay | `m1139` | `m0945` | ❌ | ✅ | ✅ | No |
| q20 | Attributed | what did Neha calculate for the trip expenses | `m1142` | `m3295` | ❌ | ❌ | ✅ | No |
| q21 | Attributed | what did Divya say about Kasol crowd | `m0942` | `m0942` | ✅ | ✅ | ✅ | No |
| q22 | Attributed | what did Karan forward about mountain cafes | `m0279` | `m0324` | ❌ | ❌ | ❌ | No |
| q23 | Attributed | what did Priya propose for the hackathon team name | `m2942` | `m2937` | ❌ | ✅ | ✅ | No |
| q24 | Attributed | what did Vikram joke about Rohan's CSS debugging | `m0011` | `m3854` | ❌ | ❌ | ❌ | No |
| q25 | Attributed | what did Sara say about Rohan's birthday dinner | `m0514` | `m0514` | ✅ | ✅ | ✅ | No |
| q26 | Temporal | what did we decide about destination in April | `m0952` | `m0940` | ❌ | ✅ | ✅ | No |
| q27 | Temporal | what did we agree about the budget in April | `m1150` | `m0825` | ❌ | ❌ | ❌ | No |
| q28 | Temporal | what travel dates were confirmed around May 1 | `m1445` | `m1437` | ❌ | ✅ | ✅ | No |
| q29 | Temporal | what birthday plan was made in March | `m0521` | `m0516` | ❌ | ✅ | ✅ | No |
| q30 | Temporal | which movie was booked in June | `m2433` | `m2430` | ❌ | ✅ | ✅ | No |
| q31 | Temporal | which hackathon team was registered in July | `m2943` | `m2940` | ❌ | ✅ | ✅ | No |
| q32 | Temporal | destination discussions on April 12 | `m0952` | `m0941` | ❌ | ✅ | ✅ | No |
| q33 | Temporal | budget discussions on April 20 | `m1150` | `m1150` | ✅ | ✅ | ✅ | No |
| q34 | Temporal | date finalization on May 1 | `m1445` | `m1430` | ❌ | ❌ | ❌ | No |
| q35 | Temporal | birthday dinner confirmation on March 24 | `m0521` | `m0516` | ❌ | ✅ | ✅ | No |
| q36 | Compound | what did Priya confirm about Big Chill in March | `m0521` | `m0521` | ✅ | ✅ | ✅ | No |
| q37 | Compound | what did Vikram book for the movie in June | `m2433` | `m2433` | ✅ | ✅ | ✅ | No |
| q38 | Compound | what did Karan submit for the hackathon in July | `m2943` | `m2936` | ❌ | ✅ | ✅ | No |
| q39 | Compound | what did Neha breakdown for costs in April | `m1142` | `m0754` | ❌ | ❌ | ❌ | No |
| q40 | Compound | what did Vikram confirm for booking in May | `m1445` | `m1438` | ❌ | ✅ | ✅ | No |