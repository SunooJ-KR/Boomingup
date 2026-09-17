// 화면 문구에 투자 판단처럼 읽히는 표현이 들어갔는지 검사한다.
// 금지 표현 목록은 docs/wording-guide.md §2를 따른다.
// 실행: npm run check:wording
import { readdirSync, readFileSync, statSync } from "node:fs";
import { extname, join } from "node:path";

const TARGET_DIRS = ["app", "components", "lib", "public/data"];
const TARGET_EXTENSIONS = new Set([".ts", ".tsx", ".json", ".css"]);
const BANNED = [
  "저평가",
  "고평가",
  "적정가",
  "유망",
  "추천",
  "투자 적격",
  "매수 타이밍",
  "매도 타이밍",
  "80% 보장",
  "재건축으로",
  "안정형",
  "성장형",
  // docs/wording-guide.md §2.2 추가 금지 표현
  "대안",
  "대체 후보",
  "국면",
  "냉각",
  "회복",
  "왜곡",
  "하방 방어",
  "수요 약화",
  "실적",
  "등급",
  "고점",
  "저점",
  "바닥",
  "꼭지",
  "회복률",
  "다음 오를",
  "확산",
  "갭 메우기",
  "키 맞추기",
  "갈아타기",
  "상급지",
  "하급지",
  "적합한 투자자",
  "투자 유형",
  "성향 진단",
  "가성비",
  "저렴한 순",
  "살 수 있는",
  "예측",
  "전망",
  "예상",
];

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) yield* walk(path);
    else if (TARGET_EXTENSIONS.has(extname(path))) yield path;
  }
}

const hits = [];
for (const dir of TARGET_DIRS) {
  for (const path of walk(dir)) {
    // 검사 스크립트 자신은 건너뛴다
    if (path.includes("check-wording")) continue;
    readFileSync(path, "utf8")
      .split("\n")
      .forEach((line, at) => {
        for (const word of BANNED) {
          if (line.includes(word)) hits.push(`${path}:${at + 1}: ${word} -> ${line.trim()}`);
        }
      });
  }
}

if (hits.length > 0) {
  console.error("금지 표현을 찾았습니다.");
  hits.forEach((hit) => console.error(`  ${hit}`));
  process.exit(1);
}

console.log("금지 표현 없음");
