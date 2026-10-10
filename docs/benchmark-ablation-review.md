# T4.3 — Benchmark retrieval và top-k

Hoàn tất 2026-10-11 localtime; run timestamps UTC2026-10-10. **6runs×60development
=360new predictions**, gồm4retrievalvariants và2additional top-k runs. Evaluator/rubric
`source-bound-evaluation-v1`, frozen100 với60dev/40test;0held-out inference.

## Protocol và kiểm soát

- Vector-only: E5, noCE; keyword-only: FTS/simple/unaccent/ts_rank_cd, noCE;
  hybridRRF: E5+FTS/RRF, noCE; hybrid+CE: sameRRFpool, pinned crossencoder.
- Fixed corpus15/307/native/OCR/quality/model fingerprint/gold; no source/index mutation.
  Same question/filter/scope roster, LLM/prompt/pins/context6/input2304/output64,
  freshness/behaviour/threshold0.55; candidate20 cho cảCEon/off.
- Core allowed axes chỉ retrieval.mode/reranker.enabled. Config fingerprints khác
  LLM/prompt/budget/candidate/filter bị reject; corpus/source/runtime/roster/hardware/
  package versions phải match. Fresh Python process pervariant,serialCPU1, sameorder,
  first-use/OS-HF-cachemixed, perrequestmodel release/reload. Singlepass, no significance
  test hoặc controlled causal latency attribution.
- Before results, selection rule: evidence/filter integrity, higher completecorrectness,
  higherfactrecall, highertaskcitationprecision, lowerp95 rồip50. Top-k4/8/12 trên
  selectedretrieval, samecontext-budget ceiling6. Effectivecontext tối đa4 khi topk4.
  Current hash-bound structural chunks là corpus version fixed trong thửtop-k này.
- Inferencebasecommit **9987bca +T4.3workingtree**; exactruntimeSourceSHA
  `a6d5fe1f955f659afa869473fe2010ac59bbecd76ac5894f0d613d98f7abc441`.
  SameWindows11/12logicalCPU/Python3.12.15, E5/CECPU2threads/GGUF4threads,
  packages locked70; optionalRAMreading unavailable, T1inventory~11,8GB.

Publicprotocol `data/manifests/t4_3_protocol.json`; immutable rawconfigs/predictions
ởignored `evals/results/t4-3-ablation/<variant>/` chứa config/commit/sourcefilehashes/
hardware/tokens/timings. CorpusSHA b213a260... vàdatasetSHA d577dcde... khớp freeze.

## Actual-answer review

4core runs tạo **77unique question/output bundles**. Assistant đọc toàn bộ77 cùng
frozen requiredfacts/actor/condition/exception requirements. Grouping chỉ khi actual
quote text/hash/ranges, sourceidentity/view/scope, question/request/clarification/
filters match; cùngstatus hoặc documenthit không đủ để ghép.

CanonicalC# là actualquoted block, map tới new localPIDs/SIDs/responseSHA từngrun.
Groupreview không gửi gold vàoModel và không copy responseSHA cũ. Full/source/offset
binding kiểm qua SQL trước group/re-score. Later120top-k responses khớp chính xác
77semanticbundles này; helper xác minh fullhash và bindsnewmembers, không tự gán
factlabels cho output mới. Mỗi360prediction có review riêng; rater không independenthuman.

Rubric nhưT4.2: fullfacts+faithfulquotes+scope/no forbiddenclaim cho correctness;
task-support citation thêm relevance. Các quote-block extra hạ precision dù primary
facts đủ. Binarysupportgold nênnDCG N/A; contrast/noanswer khôngpositive recallgold.

## Bảng4retrievalvariants

Mỗi hàng60requests/47answerable. Macrorecall/MRR trên47; tử/mẫu của quality theo
rubric; mixed-status end-to-end trên cả60, không chỉ các lượtgeneration.

| Variant | Recall@5 | Recall@10 | MRR@10 | Đúng đủ ý | Facts | Taskcitations | Rejectđúng | Rejectnhầm | p50/p95s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| vector_only |.98936 |1 |.89787 |41/47 |57/65 |53/75 |7/8 |1/47 |7.050/15.672 |
| keyword_only |.85106 |.94681 |.65674 |35/47 |49/65 |45/69 |7/8 |5/47 |5.013/11.531 |
| hybrid_rrf |.94681 |1 |.75641 |36/47 |51/65 |48/71 |8/8 |3/47 |6.572/14.032 |
| hybrid_reranked |.98936 |1 |.96454 |41/47 |57/65 |52/71 |8/8 |1/47 |13.000/20.997 |

All240:60/60perrun filterpreservation/citationrender/sourcebindingfidelity; actual
quotedblocks faithful toboundcontext. Những số này không đảm bảo questionrelevance
hoặc completeness. Keyword/vector D43 **falseanswer** từ unchangedcredit/course/
programme blocks không trả classminimum; không thấy old50threshold, nhưng status vẫn sai.

**Reranker effect:** samehybrid candidate/budget config, completecorrect36→41/47;
pairedwins D16/D27/D40/D58/D59,0pairedlosses. R5 .94681→.98936,MRR .75641→.96454,
taskcitation48/71→52/71. Cost: thêmCEactive50, observedmedianstage5.755s/p959.193s,
end-to-endp50 tăng6.572→13.000s. Sourcequality/strongfilters là commonconstraint,
không attribution toàn effect cho model mà không xét downstreampassageselection.

Vector-only cũng41/47correct, tốc độ tốt hơnCE; CE có betterMRR/taskprecision vàD43
correctabstention. HybridRRF thấp hơnvector-only trêndevelopment này; không che regression
bằng documenthit hoặc mặc định “hybrid luôn tốt hơn”. Keyword thua6fullanswers so vớivector
vàfalseanswersD43; nhanh hơn một phần vì5falseabstentions không chạyLLM.

## Top-k sweep và lựa chọn

| Hybrid+CE top-k | Đúng đủ /facts /taskcitations | p50/p95s | Input/outputtokens |
|---|---|---:|---:|
|4 |41/47;57/65;52/71 |**12.441/17.820** |25588/479 |
|8 |41/47;57/65;52/71 |13.000/20.997 |25588/479 |
|12 |41/47;57/65;52/71 |12.833/18.037 |25588/479 |

All3 cùngactualclaim bundles,8/8correctreject,1/47false,11/12clarificationfields;
top-k tăng không sửa6answerfailures hoặc D51missingstudyprogress. Rank10metrics vẫn
quan sát fullpool, không có nghĩa answercontext4 đã dùng10chunks.

**Chọn `hybrid_reranked_k4` theo predeclaredtie-break**, file
`configs/rag/t4_3_selected.json`, configSHA
`611919f4820fe719c0ae485662fc1b9ed614ef457f4818ef37e630e46fbd9216`.
`data/manifests/t4_3_selection.json` sealtimestamp/inference/review/config evidence.
Đây là developmentretrievalreference choT4.4, finalreleasefreeze sau errorfixes.
Chênh p95 giữa4/8/12 chỉ là observedsinglepass/local-load, không chứng minh causalspeedup;
samequote/tokencounts không cho phép claim generationwork giảm.

GPA/source-regression8 với selectedconfig:6supported/2correctabstain,
mainĐTBC≥8cap30/old790-only được dùng, hè1393cap12, unchangedĐiều24 và staleclassfilter
giữ đúng. Smoke all8mixedcold/warm p5014.286/p9530.652s riêng; không ghép vào60benchmark.

## Tokens và chi phí

| Run | Input /output tokens | Generationrequests | APIcostVND |
|---|---:|---:|---:|
| vector_only |28939/502 |47 |0 |
| keyword_only |26104/449 |43 |0 |
| hybrid_rrf |26364/466 |44 |0 |
| hybrid_reranked/k4/k12 mỗirun |25588/479 |46 |0 |

Actualprovider/IDsusage, output là selectionJSON, backendquotes không tínhgeneratedtokens.
Localcompute/hosting/electricity **chưa định giá**, không gộp thành APIcost0. Rawpercase,
all-sample/active stagequantiles vàcategorymetrics ở comparisonJSON/runreports.

## Failures và limits

- Selectedcaseerrors giữD33/D34/D36/D37partialfacts,D38wrongprogress/topic,D42falseabstain,
  D51missingprogress. Extra material vẫn taskprecision73.24% <target90%,multi7/12;
  bestobservedp9517.82s >trialtarget10s. T4.4 cầnfix, không relabel để đạt.
- Các biến thể khác thêmD15/D16/D27/D40/D43/D58/D59issues theo pairedCSV/JSON; fullfidelity
  không cứu wrongtopic/falseanswer. D20appendixC4 củavector/RRF thực sự corroborates20days
  nên được tínhrelevant; before-defense/archiving blocks khôngrelevant. Không đổi T4.2verdict
  vì các quotedblocks củaT4.2 khácappendixblock này.
- Commoncorpus/exposeddevelopment/manualassistantreview, onepass/no random-order repeats;
  không independent heldoutaccuracy, statisticalsignificance hoặc latencycausalestimate.
-40test vẫnfreeze/0inference; finalconfiguration chọn từdev trướcheldout. Sourcecheck snapshot
 09Oct2026/currentlegalstatusunknown/45excludedpages giữ nhưcorpus scope.

## Kiểm chứng và reproduce

-354tests:237unit/117schema-isolatedPostgreSQL,107.01s;Ruff171files/12Node/lock70/pipcheck.
- Post-study frozen100/72spans/49chunks/legacy30/19 vàactualPDF/corpus15ready/307FTS/
 15unchanged/0unfinished giữ hashes; t4_3datasetintegrity/publicationsnapshot.
- Public `t4_3_benchmark.csv`, core/fullcomparisonJSON, core/allgroupreviews,
  protocol/selection/smokeaudits; rawquotedruns/groupmap/modeltraces ignored.
- `evals/README.md` và `docs/development.md` có run/packet/review/compare/selection commands.
  Newrun cần new boundgroup signatures; output mới phải manualreview, không ép inheritedlabel.
