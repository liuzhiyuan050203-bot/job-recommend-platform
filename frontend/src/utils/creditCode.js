/** 统一社会信用代码（GB 32100-2015）：18 位，第 18 位为校验码，不含 I、O、S、V、Z。 */
const CHARSET = '0123456789ABCDEFGHJKLMNPQRTUWXY'
const WEIGHTS = [1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28]
const PATTERN = /^[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}$/

export function normalizeCreditCode(value) {
  return String(value || '').trim().toUpperCase()
}

export function isValidCreditCode(value) {
  const code = normalizeCreditCode(value)
  if (!PATTERN.test(code)) return false
  let sum = 0
  for (let i = 0; i < 17; i += 1) {
    const index = CHARSET.indexOf(code[i])
    if (index < 0) return false
    sum += index * WEIGHTS[i]
  }
  let check = 31 - (sum % 31)
  if (check === 31) check = 0
  return code[17] === CHARSET[check]
}

export const CREDIT_CODE_MESSAGE = '统一社会信用代码须为 18 位并符合校验位规则（不含 I、O、S、V、Z）'
