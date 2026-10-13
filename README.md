# RegulaRAG — tra cứu quy định UIT bằng nguồn có citation

FastAPI phục vụ **API và native web UI chung một server**. Retrieval E5-small +PostgreSQL
FTS/RRF +CPUcross-encoder; QwenGGUF chọn passage IDs, backend dựng quotedanswer với
source/Unicodeoffset/SHA. Có clarification, explicitfilters vàsource/latest guards.

## Kết quả đã đo

M4: development47/47answerable đúng đủ ý, held-out **19/28**, citation task-support
**29/108**, đúng từ chối **0/7**; held-outp95 **32.707s** trên máyCPUđãghi nhận.
Đây là localdemo/evaluation snapshot, chất lượng tổng quát chưađạt mục tiêu.
Phương pháp/failures: [T4.4 report](docs/error-analysis-review.md).
Trace/runtime: [T5.2 report](docs/observability-review.md).

## Chạy container local

Yêu cầu: DockerDesktop/Linuxcontainers (amd64), khoảng6GBRAM choDocker, đủdisk choimage/
modelcache, truy cậpPyPI/CPUwheel/HuggingFace khi bootstrap. LocalAPI publish **127.0.0.1:8001**.
DB data ởnamedvolume;weights/source/rawOCR không nằm trongimage/Git. Modelcache offline saubootstrap.

### 1. Image và database

```powershell
docker compose --profile app build api
docker compose up -d --wait db
docker compose --profile tools run --rm tools python scripts/migrate.py
```

Docker dùng Python3.12.15 vàsame70pinnedCPUpackages trongrequirements.lock; models tải riêng.
Image chứa installedwheel vàwebassets; khôngnpm/frontendbuild hoặcserver riêng.
Health kiểmdatabase/pgvector, **không** chứng minh model/corpus đãready.

### 2. Model cache — bước explicit

```powershell
docker compose --profile tools run --rm -e HF_HUB_OFFLINE=0 -e TRANSFORMERS_OFFLINE=0 tools python scripts/download_models.py
docker compose --profile tools run --rm tools python scripts/download_models.py --check-only
```

Script dùng exactrevisions trongconfigs/rag/final.json vàBGEtokenizerpin; không tải weights
trongdockerbuild/APIstartup. Cache defaultnamedvolume. Có thể đặt `REGULARAG_HF_CACHE`
trỏ tới HuggingFacehomecache đãcó, ví dụWindows`C:/Users/<user>/.cache/huggingface`.
Giữcache cấu trúc`hub/models--.../snapshots/<revision>/...`, không đặtfileweights tùy ý.

### 3. PDFs và approved publication — không tự approve

FullsourcePDFs/OCR/artifacts không được redistribute trongrepo/image. Để có corpus demo:

- Có15PDFs đúng`local_path`/SHA trong `data/manifests/documents.csv` ở `data/raw/uit/p0/`.
- Có reviewedartifact directories `data/processed/m2-publication/<document_id>/`
  vớimetadata/chunks/pages củasupportedM2scope; lấy từoperator đãreview hoặc thực hiện
  parse/OCR/post-edit/page/layoutreview theo [developmentguide](docs/development.md).
- Missing/corrupt/unapproved inputs bịchặn; không đổihash/gold hoặcapprovechỉ vìconfidence.
  Những inputs này làprerequisite rõ ràng, **freshclone chưa tự có RAGcorpus**.

```powershell
docker compose --profile tools run --rm tools python scripts/check_setup_inputs.py
docker compose --profile tools run --rm tools python scripts/index_baseline.py
```

Indexer đi quaatomicingestion lifecycle. Lượt đầu embed/index307approvedchunks/15documents;
lượt sau unchanged nếusource/config/hash/quality khớp. Không OCR lại hoặcre-index để làmbenchmarksđạt.
DB mới là một deployment riêng; originalfrozenM4measurement thuộcsourceversion/corpusrecordđãđo.

### 4. API/UI và checks

```powershell
docker compose --profile app up -d --wait api
```

Mở **http://127.0.0.1:8001/**, docs **http://127.0.0.1:8001/docs**.
Health **http://127.0.0.1:8001/health**; mỗiask có`request_id`/`X-Request-ID` đểinspectJSONtrace.

```powershell
# Trong Conda ragschool nếu chạy checks từhost:
python scripts/check_container.py --base-url http://127.0.0.1:8001
python scripts/check_container.py --base-url http://127.0.0.1:8001 --real --output-dir data/processed/<new-container-check> --summary data/manifests/<new-ID-only-check.json>
```

`--real` dùngdevelopmentcontrols hè12/GPA30/old-onlyguard, không dùngT01–T40heldout.
NativeWindowsdemo8000 vẫn được hướng dẫn ở [demo guide](docs/demo-guide.md).

## Cấu hình và dừng

Compose đọc `.env`/environment. Các giá trị mẫu là localdefaults; `.env` thật ngoàiGit.

- `REGULARAG_API_PORT`: default8001;localhostbinding.
- `POSTGRES_PORT`: default5432; đổi khi chạy một projectDB mới.
- `REGULARAG_CONTAINER_DATABASE_URL`: DSN bên trongcontainer, defaulthost`db`.
  Nếu đổiPGcredentials/database, cung cấpDSN tương ứng (URIencode nếu cần).
- `REGULARAG_HF_CACHE`: namedcache hoặchostHuggingFacehomepath.

```powershell
docker compose --profile app logs --no-color
docker compose --profile app down
```

Không thêm`--volumes` choDB/cachedemo nếu muốngiữ dữliệu. Logretention dooperator quản lý,
trace chỉboundedmetadata; rawresponses/models/OCR ngoàiGit theo`.gitignore`/`.dockerignore`.

## Tests và CI

Local checks trongConda `ragschool`:

```powershell
python -m ruff check .
python -m ruff format --check .
$env:REGULARAG_RUN_DB_TESTS = "1"
python -m pytest
node --test tests/ui/contract.test.mjs
python scripts/check_environment.py
python -m pip check
```

GitHubActions [CI workflow](.github/workflows/ci.yml): pinnedPython/packages/actions/PGimage,
Ruff/dependencychecks +fullunit/schema-isolatedDBtests +UIcontracts; **LLM/HFmodels mocked**,
downloadguard/offline/emptycache. Một job khácbuild/startpackagedUI/API trênfreshCIdatabase
với explicitmigrations, không tảimodelweights hoặcgọiheldout. Setup thủ công vàLinuxruntime
validation không bịgiấu dưới tuyênbố“một lệnh”.

Chi tiếtdata/setup/guards: [docs/development.md](docs/development.md).
Tiến độ vàbàn giao: [docs/progress.md](docs/progress.md), [docs/handoff.md](docs/handoff.md).
