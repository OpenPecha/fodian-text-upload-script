 # Text Upload Workflow

Simple steps to prepare input JSON and upload texts, instances, and translations.

## 1) Build input JSON folders
Source files live in `json/`. This script creates `input_json/<incipit_title>/` folders with:
- `text_metadata.json`
- `instance_payload.json`
- `translation_payloads.json` (only if translations exist)

Run:
```bash
python text_separater/build_input_json.py
```

## 2) Check BDRC (optional)
Check a single folder:
```bash
python text_separater/bdrc_checker.py --input-folder "/path/to/input_json/<incipit_title>"
```

Check all folders:
```bash
python text_separater/bdrc_checker.py --all --input-root "/home/lungsang/Desktop/fodian_text_upload_task/input_json"
```
Save results for reuse: ***********************************
```bash
python text_separater/bdrc_checker.py --all --input-root "/home/lungsang/Desktop/fodian_text_upload_task/input_json" --output "/home/lungsang/Desktop/fodian_text_upload_task/bdrc_cache.json"
```

## 3) Upload text + instance
Upload a single folder:
```bash
python text_separater/text_upload.py --input-folder "/path/to/input_json/<incipit_title>" --skip-existing-bdrc
```

Upload all folders:
```bash
python text_separater/text_upload.py --all --input-root "/home/lungsang/Desktop/fodian_text_upload_task/input_json" --skip-existing-bdrc
```

Use saved BDRC results (avoid API lookups when skipping existing): ***************************
```bash 
python text_separater/text_upload.py --all --input-root "/home/lungsang/Desktop/fodian_text_upload_task/input_json" --skip-existing-bdrc --bdrc-cache "/home/lungsang/Desktop/fodian_text_upload_task/bdrc_cache.json"
```

## 4) Upload translations
Use `translation_payloads.json` and the instance ids returned from step 3.

Example translation plan (add `instance_id`):
```json
[
  {
    "instance_id": "ABC12345678",
    "language": "en",
    "content": "Translated text...",
    "title": "Translated Title",
    "source": "Source of the translation"
  }
]
```

Run (single file):
```bash
python text_separater/translation_upload.py --input /path/to/translation_plan.json
```

Run (all folders): *******************************************
```bash
for payload in "/home/lungsang/Desktop/fodian_text_upload_task/input_json"/*/translation_payloads.json; do \
  python text_separater/translation_upload.py --input "$payload"; \
done
```

## Notes
- API base URL defaults to `https://api-aq25662yyq-uc.a.run.app`.
- Content must be a single string. Arrays are flattened and joined with `\n`.
- Use `--output <file>` with any script to save results.
