# 빌드 방법

번역 대본과 원문은 저장소에 없습니다. 아래는 자신이 가진 원본과 번역 파일로 다시 빌드하는 절차입니다.

## 준비물
- 원본 `Lost Heroes (Bonus Edition) (Japan) (eShop).cia` (MD5 `632e0bf931eff99aec589289787d930f`)
- Batch CIA 3DS Decryptor의 `bin` 폴더(`decrypt.exe`, `makerom.exe`). 경로를 환경 변수 `DECRYPTOR_BIN`으로 지정합니다.
- Python 3.12+: `pip install pillow numpy fonttools`
- .NET 6 SDK(`tools/mobi`, `tools/ocr` 빌드용)
- Git Bash 같은 bash 환경
- 글꼴 `NanumSquareNeo-*.ttf`, `SeoulHangang*.ttf`. 보충 글꼴로 Windows의 `malgunbd.ttf`도 씁니다.

## 폴더 구성
```
<작업 폴더>/
  Lost Heroes (Bonus Edition) (Japan) (eShop).cia
  NanumSquareNeo-*.ttf, SeoulHangang*.ttf
  <이 저장소>/
    tools/
    tr/            in/*.json, out/*.json, glossary.json, staff_ko.json   (번역, 저장소 미포함)
    units.json, refs.json, all_jp.json, jtab.txt, base363.txt, packs.json   (추출 결과)
    texidx.json, uv.json, imgout/   (그림 글자 결과, spec_*.txt로 생성)
```

## 순서
1. **도구 빌드:**
   - `dotnet build -c Release -o tools/mobi/bin tools/mobi`
   - `dotnet build -c Release -o tools/ocr/out tools/ocr`
2. **추출:** `tools/fullbuild.sh` 앞부분이 복호화와 `ext/romfs` 추출을 합니다. 따로 하려면 `tools/ctr.py`의 함수를 씁니다.
3. **텍스트:**
   - 폰트 문자표를 만듭니다: `tools/align.py`, OCR, `tools/vote.py`, `tools/combine.py` → `jtab.txt`
   - 원문을 뽑습니다: `python tools/extract_all.py` → `all_jp.json`, 이어서 `python tools/units.py` → `units.json`, `refs.json`
   - 번역합니다: `tr/in/*.json`을 번역해 `tr/out/*.json` = `{id: 한국어}`로 만든 뒤 `python tools/merge.py`를 실행합니다.
4. **그림 글자:**
   - `python tools/texdump.py`로 텍스처를 추출하고 조각 좌표(`uv.json`)를 만듭니다.
   - `spec_*.txt` 사양서를 작성합니다(`docs/IMAGE_GUIDE.md`).
   - `python tools/imgko.py spec_x.txt`로 `imgout/`을 만듭니다.
5. **스태프롤:** `tr/staff_ko.json`을 작성합니다. 번호는 `StaffRoll.mbb` 표0의 항목 번호입니다.
6. **전체 빌드:** `DECRYPTOR_BIN=... tools/fullbuild.sh` → `build/lh1_ko.ncch`. 텍스트·폰트·팩·그림·스태프롤·동영상이 모두 들어갑니다.
7. **CIA:** `makerom -f cia -ignoresign -target p -o 한글.cia -i build/lh1_ko.ncch:0:0 -i dec/bin/lh1.1.ncch:1:1`
8. **차분:** `xdelta3 -e -0 -S none -A -s 원본.cia 한글.cia 패치.xdelta`

## 검증
- `tools/run.sh <cxi> "<shot.png> <키…>"`: Azahar 포터블 사본을 `azahar/azahar_lh1.exe`로 실행해 키를 보내고 스크린샷을 찍습니다.
- 경로에 한글이 있으면 Azahar가 제대로 동작하지 않습니다. 영문 경로의 디렉터리 정션을 쓰세요.
