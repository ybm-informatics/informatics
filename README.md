# NCIC 중학교 정보 교육과정 수집기

NCIC에서 2022 개정 교육과정 별책 10 PDF를 수동으로 가져와 중학교 정보 부분을 구조화한다. 수집 결과는 검토용 staging에 먼저 저장되며, 편집자가 확인한 뒤 기준본으로 승인한다.

## 설치

```powershell
python -m pip install -r requirements.txt
```

## 사용

NCIC에서 공식 PDF를 가져와 구조화한다.

```powershell
python -m ncic_curriculum import
```

로컬 PDF나 PDF 주소를 직접 입력할 수도 있다.

```powershell
python -m ncic_curriculum import "C:\자료\별책10.pdf"
python -m ncic_curriculum import "https://example.com/별책10.pdf"
```

생성 결과를 검사하고 승인한다.

```powershell
python -m ncic_curriculum validate
python -m ncic_curriculum approve
```

## 생성 파일

```text
data/ncic/
├─ raw/                         내려받은 공식 PDF
├─ staging/curriculum.json      승인 전 구조화 데이터
├─ reports/review.csv           편집자 검토표
├─ reports/changes.json         기존 기준본과의 변경 비교
├─ reports/errors.json          오류·누락 보고서
└─ approved/
   ├─ current.json              현재 기준본
   └─ versions/                 승인된 버전 이력
```

`review.csv`는 Excel에서 바로 열 수 있도록 UTF-8 BOM 형식으로 저장한다. `approve`는 오류 보고서에 차단 오류가 없을 때만 실행된다.

## 이용 조건

시범 버전은 공개된 NCIC 자료를 비영리 연구 목적으로 수동 수집한다. 결과를 판매 자료나 상용 웹 패키지에 사용할 때는 원문의 공공누리 표시와 NCIC 이용 조건을 다시 확인하고 필요한 이용 허락을 받아야 한다.
