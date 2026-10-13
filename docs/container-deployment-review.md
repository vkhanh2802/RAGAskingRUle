# T5.3 — Docker, CI và local deployment

Ngày kiểm chứng local: **2026-10-13**. Local packaging/setup/deployment gates đạt;
hosted GitHub Actions đang chờ commit/push được người dùng cho phép.

## Đóng gói

- Python3.12.15slim/bookworm, Dockerfrontend vàPGvector17 images pin theo digest;
  lock70versions củaWindows được dry-run và install/import trênLinuxamd64, không đổiPython pins.
- Multistage builder cài70CPUpackages vàoVENV, buildprojectwheel bằngHatchling1.27.0,
  copyVENV sangruntime. Buildertools không đưa vào transferredVENV.
- Wheel cóAPI/nativeUI/assets; kiểm `.mjs`MIME/HTML quaHTTP thật. Không frontendbuild/service riêng.
- RuntimeUID10001, singleUvicornworker/serializedCPUmodels, readonlyroot/tmpfs,
  sourcesrawmountreadonly, HFCachenamedvolume hoặchostcache, `--no-access-log`/tracev1.
- `.dockerignore`buildallowlist loại `.env`/PDFs/fullOCR/processed/modelweights/traces;
  bareimageinspectionimportTorchCPU/Llamagrammar/UIassets và70versionchecks đạt.
- `compose.yaml`: defaultdb-only tương thíchexistingworkflow; profiles`app`/`tools`explicit.
  API/UI publish127.0.0.1:8001,PG127.0.0.1:5432. Tools chạy riêng migration/cache/inputcheck/index.

Testedlocalimage `sha256:5dde080c5e08ef2d1c7bb4d28ea1af5d2ad2e4c55ceb527f60529eb848d37afd`,
506300553bytes (Docker-reported), userregularag/UID10001; Torch2.14.1+cpu/Llama0.3.36.
Image làworking-treepackaging sauT5.2, không claimbyteidentity vớiM4measuredsourceversion.

## Setup rõ từng bước

[README.md](../README.md) làrunbook: buildimage →startdb →migrate →explicitmodeldownload/check
→verifyoperatorPDFs/approvedartifacts →index →startAPI/UI →HTTPchecks.

- `download_models.py`: fourexactrevisioncomponents(BGEtokenizer/E5/CE/GGUF);
  BGEweights khôngdownload, othermodelassets cóallowpatterns; `--check-only` khôngfetch.
- Đãbootstrap **namedvolume mới** bằngonlineoverrides vàcheckoffline4/4ready.
  Dockerbuild/APIstartup không gọibootstrap; cachedabsence không biến thànhfakeanswer.
- `check_setup_inputs.py` đọc15rawPDFbytes/SHA và `load_processed`quality/source/chunkhash/
  provenanceguards. Cácinputs supplied ngoàiGit/image, không tựapproveOCR/layout bằngconfidence.
- Freshclone chưa có cácpublicationinputs. Saukhi operator cung cấp reviewedinputs, freshDBsetup
  đãtái lập đủ15/307. Không tuyênbốclone→fullRAG“một lệnh” hoặc tựnormalize/approve sources.

## Database mới và idempotence

Ownedproofproject`regularag-t5-3-setup`, freshvolume/network,hostports55432/8002;
khôngindexlạioriginalfrozenDB để làmmeasurementđạt.

1. `migrate.py`firstapply001–006;secondrunskip6.
2. Inputcheck15PDFs/307approvedchunks đạt.
3. `index_baseline.py`firstindex15/307 vớiLinuxCPU/E5pins;secondrun15unchanged.
4. Publicationaudit307unique/307FTS/0unfinished,103approved/40native/45excluded;
   19legacygoldchunks source/text/hash unchanged.
5. RealHTTPsmoke31assertions/6developmentrequests đạt: summer12/1393,
   GPA30/mainsemester/unchanged790view,old-onlyfilter/latestabstain,clarificationaxes,
   invalidtopk422,header/bodyID,sourceoffset/hash/render fidelity.

Originalfrozen100/datasetd577.../72spans/49chunks/legacy30/19 kiểm read-only vẫnđạt.
NewDBdeploymentmetadata/paths/embeddings không được rebindvàoM4freeze; các measurement/predictions/
reviews/sourceversion cũ được giữ. T5.3 có0newheldoutinference.

## Deploy chính local

DefaultComposeproject`regularag` dùngoriginaldatabasevolume vàfreshnamedHFCachenamedvolume;
DBmigrations6skip. API/UI **http://127.0.0.1:8001/** đãhealthy.
DeployrealHTTPchecks31assertions/6developmentcontrols giốngproofproject đạt;
`data/manifests/t5_3_deployed_container_checks.json`.
NativeWindowsdemo8000 làentrypoint khác trongdocs/demo-guide, containerdefaultport8001.
No publiccloud/APIpaid deployment; conditionalpaidpublicrate-limit item chưaapplicable.

## CI definition và local gates

`.github/workflows/ci.yml` có2jobs trênUbuntu24.04,actionsSHA-pinned/checkoutcredentialsnotpersisted:

- `quality`: Python3.12.15/lock70, Ruff/format/dependencychecks, freshPGmigration,
  **fullunit+117schema-isolatedPGtests**, Node22UIcontracts.
  `REGULARAG_CI_NO_MODELS=1`, emptyHFcache/offline vàHubdownloadguard; LLM/embedding mocks cósẵn.
- `container-startup`: buildruntimeimage, ComposeDBhealthy, explicitmigration,
  startAPI/read-onlyroot, model-freepackagedUI/API/clarification/out-of-scope/422smoke.
  Khôngtảimodelweights/rerunheldout trongCI;cleanupvolumes chỉ trongisolatedGHrunner.

LocalConda`ragschool`CI-equivalenttests vớiemptycache/downloadguard **387passed**
(270unit/117DB),13Nodecontracts,Ruffcheck/format195files,pipcheck/lock70 đạt.
Runtime bareimage/Composeconfig/realcache/freshsetup/deploymentchecks đạt.
HostedCI status chưa được gọi“xanh”trước khiworkflowđượcpush/chạy; sẽ ghi runURL/kếtquả thật.

## Failures retained

`t5_3_pilot_failures.json` vàignoredfailedcheckdirs giữ:

- FirstfreshHTTPsmoke MIMEassertfail: backendactualMIME200/text/javascript đúng,
  helperdùngcase-sensitiveHTTPheaderlookup. Normalizeheaderkeys trongchecker, giữMIME/IDchecks,
  rerun ởnewdirectory; không bỏcheck/sửabackend/gold chođạt.
- Follow-upsession HTTPconnectionrefused trước khiDockercontainershealthystarted;
  `compose --profile app up -d --wait api` recovery, verifyfreshdeploymentrunv2.

## Artifacts/giới hạn

PublicID-onlyevidence: `t5_3_local_packaging_validation.json`,
`t5_3_fresh_container_checks.json`, `t5_3_deployed_container_checks.json`,
`t5_3_pilot_failures.json`, `t5_3_dataset_integrity.json`.
Rawresponses/approvedtext/logs ởignored`data/processed/t5-3-*`;
`t5-3-fresh-publication.json` chứaoperatorpublicationdetails.

M4qualitylimits (test19/28correct/taskcitation29/108/reject0/7) còn tồn tại,
deployment/CIgates không thay semanticbenchmark hoặc chứng nhậnlegalcurrent/fullcoverage.
CrossOSmodelruntime checks không được dùng đểclaim Windowsbenchmark accuracy/latency.
APIhealth làDB/pgvector health, không model/corpusreadiness. NativeOCR/review vẫn cầnsetup riêng,
được mô tả ởdevelopmentguide. Loggerrotation/retention dooperator quản lý.

Tiếp theo sauhostedCI/chốtT5.3: **T5.4—READMEportfolio/video/phỏng vấn**.
