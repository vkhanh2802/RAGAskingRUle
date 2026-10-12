# T5.2 — Request correlation và pipeline tracing

Ngày hoàn tất: **2026-10-12**. Trace schema **`pipeline-trace-v1`**.

## Luồng đã triển khai

- Middleware ASGI cấp UUID mới cho mỗi HTTPrequest, trả `X-Request-ID`. Với ask thành công
  HTTP200, body có `request_id`; validation422/backend503/unexpected500 vẫn có responseheader.
  Callerheader không được dùng làm ID củaserver. Không có requestbody/headers trong trace.
- `ContextVar` truyền cùng trace từ asyncmiddleware sang FastAPI syncworker rồi service,
  retrieval/reranker/generator. Mỗi request có spanID/parentID/startms/duration/status/error_type.
  Inferencequeue được đo riêng khi service chờ model lock.
- JSONevent từ `regularag.trace` ởINFO, metadata configSHA/pipeline/modelnames/revisions/
  promptversion/actualimplementation, dưới cùngrequestID với application/librarylogs.
- Pipeline: scope →embed →dense/keyword →fusion/focus/freshness →rerank →guardedorder →top-k
  →contextselect/guards →budget/preparedpassages →generate →resolve →sources/response/release.
  Before/afterCE, finalobligationorder vàeffectivecontext là các snapshot khác nhau.
- Registry chỉ ghi PIDs/SIDs/chunkIDs/Unicodeoffsets/SHA/dependencyIDs. `required_support`,
  modelselectedPIDs, resolved/citedIDs, guardreason chỉ ra đoạn nào bị bỏ hoặc chọn thiếu.
- Input/outputtokens lấy từ `GeneratedAnswer` providerusage, đã sum retries ởadapter;
  budgetinputtokens là một field riêng. Khônggeneration→0, called nhưng unknown→null.
  Attemptcount giữ nguyên. APIcostlocalbackend0VND; compute/hosting chưa định giá.
- Trace sink failure được bỏ qua để response/inference không thành HTTPerror vì telemetry.
  Không thêm embedding/retrieval/generation call để ghi trace; unitcounter verify mỗi delegate1call.

## Nội dung và giới hạn logs

Allowlist fields, tối đa64spans/request,100chunkrows/snapshot,16passages/registry,
spanattribute strings160chars; `omitted_spans`/`*_omitted` ghi việc cắt.
Model/promptmetadata lấy từ operatorRAGconfig. Thường20candidate/30spans.
Không log query/answer/source text/prompt/vector/rawmodeloutput/headers/DSN hoặc exceptionmessage.
Filter/scope chỉ fieldnames, không actualcaller values; values vẫn có ở request/response local củaclient.
Exception chỉ classname; application logs có ID. HTTPclient INFO/DEBUG tắt để tránh queryURLs;
chạyUvicorn `--no-access-log` dùng applicationJSONtrace choask.

Parents bao gồm children, **không cộng các duration thành e2e**. Contextprepare có cả
tokenbudgeting và model/tokenizer load; `generate` chỉ adapter.generate, không toàngenerationstage.
`largest_observed_leaf_stage` là stage lá chậm nhất được đo, không causalperformance attribution
hay calibratedconfidence. Traces không tự chấm semanticcorrectness.

## Tìm trace từ một đáp án sai

1. Lấy `response.request_id` trong JSONexport/Chi tiếtresponse hoặc HTTPheader `X-Request-ID`.
2. Tra operatorlog bằng ID này; không cần log fullquestion/source vào serverlog.
3. So candidateorder →CEorder →guardedorder →top-k →context/registry →selected/resolved/citedPIDs.
4. Xem guardreason/failedspan vàtiming lá. Đối chiếu source/offsets trong response để reviewmeaning.

Trong Conda `ragschool`:

```powershell
python scripts/inspect_trace.py --log data/processed/t5-2-observability/events.jsonl --request-id c05ebcad-9969-4d19-8d05-05c89350cad2 --output data/processed/<existing-directory>/diagnostic.json
```

Tool chọn đúng một completeJSONtrace theo UUID/schema/logger; bỏ nonJSONstartup lines,
rejectmissing/duplicateIDs. Output chứametadata/timeline/IDs, không nguồn/modeltext.
Directoryoutput phải tồn tại, không overwrite output cũ.

Ví dụ realHTTP đã kiểm chứng:

```powershell
python scripts/inspect_trace.py --log data/processed/t5-2-live-api/stderr.log --request-id 9e9fd74e-d3f1-46c8-aabd-dde7d4cd7d19
```

## Evidence / kiểm chứng

`scripts/check_observability.py` chạy actuallocalDB/E5/CE/Qwen với4developmentcontrols,
một declaredwrong-selector fixture dùngrealretrieval/budgeting, một backenderrorfixture,
một422validation. **7/7tracecontracts đạt**, không làaccuracybenchmark.

| Case | Quan sát |
|---|---|
| O01 signaturepositive |1393effectivity+signature,citedP1/P2;592input/11output;30spans; cold`query.embed`30.904s |
| O02 knownextraquote probe |159correct10topics nhưngmodelselected/citedP1/P3, cóextrafamilyrule;`required_support=[]`;generate12.450s |
| O03 clarification |Missing_scope trướcretrieval/generate;0tokens;requiredscopefields cóstudy_progress |
| O04 old-onlyfilter |Blocked790classsize/1393excluded;generate skipped/0tokens;rerank12.026s |
| O05 wrongselector fixture |CE/context córule+signature; fixture chỉP2;`evidence.resolve`incomplete_passage_support;usageunknownnull |
| O06 unavailablefixture |HTTP503;`retrieve`failed/OSError;exceptionmessagecanary không trongtrace |
| O07 invalidrequest |HTTP422/ID;rootHTTPspan,không modelcall;question/headercanaries không log |

O05 là fixture, **không claimQwen sinh sai trong caseđó**; metadata có actualimplementation
`SignatureOnlySelector`. O02 là lỗi extraquote từ Qwen thật còn tồn tại, chỉ diagnosis.
Để xem nghĩa đoạn ngoài task dùng ignoredO02response; trace chỉ metadata.

LiveUvicorn8000: HTTP200/responseID=headerID=JSONlogID; ID
`9e9fd74e-d3f1-46c8-aabd-dde7d4cd7d19`, inspector tìmcomplete30spans từpersistentstderr.
Cited1393chunk0002/0000;592/11tokens,e2e52.526s/coldembed30.836s. Đây làstartupdiagnostic,
không đối chiếu nhưperformancebenchmark cùngT4.4.

- **383pytest**:266unit/117schema-isolatedPostgreSQL;13newtrace/privacy/queue/correlation tests.
- **13Nodecontracts**, Ruffcheck/format186files, lock70/pipcheck đạt; không thêmdependency.
- Concurrency test hai HTTPrequests phân biệtIDs/traces, modelqueuewait≥20ms trongfixture;
  traceon/off giữactualanswer/sources/passages, unknownvszero usage vàfailedsinkHTTP200.
- Privacycanaries question/source/model/header/exception đều không ởapplicationtrace;
  standardFastAPI422response có thểechoinvalidinput cho caller, không đưa responsebody vàologs.
- Unexpected500 giữgenericJSON/ID/type-only trace; tests bao gồm422/503/500 vàcontextreset.
- Read-only frozen100/72spans/49chunks/legacy30/19 giữhash; corpus15ready/307unique/307FTS/
  15unchanged/0unfinished vàsupported103approved/40native/45excluded giữ nguyên.
- ExistingStarlette/httpx deprecationwarning còn được ghi nhận.

Artifacts public: `t5_2_observability_checks.json`, `t5_2_live_trace_check.json`,
`t5_2_dataset_integrity.json`, `t5_2_publication_snapshot.json` (metadata/IDs only).
Actualresponses/events/inspectedtraces/logs ởignored `data/processed/t5-2-*`.

## Cấu hình vận hành

```powershell
$env:REGULARAG_RAG_CONFIG_PATH = "configs/rag/final.json"
$env:REGULARAG_LOG_LEVEL = "INFO"
$env:REGULARAG_PIPELINE_TRACING_ENABLED = "true"
python -m uvicorn regularag.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Đặttraceflagfalse để tắtcollect/emission; HTTPrequestID vẫn có. Traceevent làINFO nên cần
loglevelINFO khi muốninspect. stdout/stderr có thểredirect vàoignoredlocaldirectory đãtạo;
logretention/rotation hiện dooperator quản lý. Không có traceDB/centralizedtelemetry backend.
Clientabort không hủyinference; backendtrace có thể hoàn tất saukhi clientdừngchờ.

Optional **Langfuse deferred**: localJSON/CLI đạtmandatorycriterion, không cài package hoặc
gửiinput/source/modelcontent ra externalservice. Adapter/storage/retention có thể làm riêng khi cần.

## T5.2 và frozen M4 evidence

Instrumentation tạo **sourceversion mới saucommitM4 `221ee6f`**; model/promptconfig/
ranking/guards/selection/Gold giữnguyên. Đây không phải rerun benchmark saufix.
Original `t4_4_release_freeze.json`/ledger/predictions/reviews không được cậpnhật theo code mới;
exactbytecheck củaM4 phải dùng sourceversion đoởcommit221ee6f với recordedfileSHA/lineendings.
Currentinstrumentedcode sẽ mismatchoriginalsourcefreeze đúngthiếtkế; không bypass verifier.
T5.2 có **0held-out inference**, tổngprojectvẫn40requests từM4. M4qualitylimitations vẫn tồn tại.

Nghiệm thuT5.2 đạt: từresponseID truy ra chunk/CEorder/context/selection/failure vàstagechậm;
metadata/tokens/cost có provenance vàcontentlimits. Bước kế tiếp **T5.3—Docker/CI/deployment**.
