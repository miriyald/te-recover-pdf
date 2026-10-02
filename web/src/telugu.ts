const CONSONANT = "[\\u0C15-\\u0C39\\u0C58-\\u0C5A]";
const VIRAMA = "\\u0C4D";
const VOWEL_SIGN = "[\\u0C3E-\\u0C4C\\u0C55\\u0C56\\u0C62\\u0C63]";
const SUBSCRIPTS = `(?:${VIRAMA}${CONSONANT})+`;
const PRE_BASE = "\\u25CC";
const ZWNJ = "\\u200C";

const SIGN_BEFORE_SUBSCRIPT = new RegExp(`((?:${VOWEL_SIGN})+)(${SUBSCRIPTS})`, "gu");
const SPACE_BEFORE_MARK = new RegExp(` +(?=${VOWEL_SIGN}|${VIRAMA})`, "gu");
const PRE_BASE_BEFORE_CLUSTER = new RegExp(`${PRE_BASE}((?:${VIRAMA}${CONSONANT})+)(${CONSONANT}(?:${VIRAMA}${CONSONANT})*)`, "gu");
const PRE_BASE_SIGN = new RegExp(`${PRE_BASE}((?:${VOWEL_SIGN})+)(${CONSONANT})`, "gu");
const VISIBLE_VIRAMA_BEFORE_SUBSCRIPT = new RegExp(`(${VIRAMA}${ZWNJ})(${SUBSCRIPTS})`, "gu");
const VIRAMA_WITHOUT_CONSONANT = new RegExp(`${VIRAMA}(?!${ZWNJ}|${CONSONANT})`, "gu");
const SUBSCRIPT_RUN = new RegExp(SUBSCRIPTS, "gu");
const SUBSCRIPT = new RegExp(`${VIRAMA}${CONSONANT}`, "gu");
const LATE_SUBSCRIPTS = new Map([["్ర", 1], ["్య", 2]]);

function orderedSubscripts(run: string): string {
  const subscripts = run.match(SUBSCRIPT) ?? [];
  return subscripts.sort((left, right) => (LATE_SUBSCRIPTS.get(left) ?? 0) - (LATE_SUBSCRIPTS.get(right) ?? 0)).join("");
}

export function normalise(text: string): string {
  const spaced = text.replace(SPACE_BEFORE_MARK, "");
  const unmarked = spaced.replace(PRE_BASE_SIGN, "$2$1").replace(PRE_BASE_BEFORE_CLUSTER, "$2$1");
  const reordered = unmarked.replace(SIGN_BEFORE_SUBSCRIPT, "$2$1").replace(VISIBLE_VIRAMA_BEFORE_SUBSCRIPT, "$2$1");
  return reordered.replace(SUBSCRIPT_RUN, orderedSubscripts).normalize("NFC");
}

export function markVisibleVirama(text: string): string {
  return text.replace(VIRAMA_WITHOUT_CONSONANT, "్‌");
}
