/**
 * Iranian mobile-number masking, for the PII reveal flow.
 *
 * The advisor's own phone input is plain (they are filing the listing), so this
 * masks a *stored* number — the owner's — behind a reveal button that only takes
 * the digits to the network after an explicit, per-card press.
 */

const IRAN_MOBILE_RE = /^(?:\+98|0098|98|0)?9\d{9}$/;

/** «09121234567» -> "09121234567", folding the Persian/Arabic digits a form may carry. */
export function normalizePhone(input: string): string {
  const folded = Array.from(input)
    .map((char) => DIGIT_FOLD[char] ?? char)
    .join('');
  return folded.replace(/[^\d+]/g, '');
}

const DIGIT_FOLD: Record<string, string> = {
  '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
  '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
  '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
  '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
};

/** True for an Iranian mobile number, with or without the +98 / 0098 prefix. */
export function isIranMobile(input: string): boolean {
  return IRAN_MOBILE_RE.test(normalizePhone(input));
}

/**
 * The dialable E.164 form, so a masked reveal hits the tel: link correctly.
 *
 * Shares :func:`localForm` with the masker so the two can never disagree on
 * what the "digits" of a number are.
 */
export function toE164(input: string): string {
  return `+98${localForm(input)}`;
}

/**
 * «۰۹۱۲••••۴۵۶۷».
 *
 * Four mask bullets and the last four digits: enough for an advisor to confirm
 * they dialed the right owner, and no more. The country prefix is folded away
 * first, so a ``+98`` or ``0098`` form masks the subscriber digits rather than
 * exposing the prefix as the "recognisable" head -- a mask whose first digits
 * are always «۰۹۸» tells the reader nothing about which number it is.
 *
 * Anything that is not an Iranian mobile number is folded to its local form
 * and masked the same way, so an unparseable value never renders in the clear.
 */
export function maskPhone(input: string): string {
  const local = localForm(input);
  if (local.length === 10) {
    // «۰۹۱۲••••۴۵۶۷»: the leading zero plus the first three digits are what an
    // advisor reads out, so they stay; the middle four are what is hidden.
    return toPersian(`0${local.slice(0, 3)}••••${local.slice(-4)}`);
  }
  if (local.length <= 1) return toPersian(local) || '';
  return `${toPersian(local.slice(0, 1))}••${toPersian(local.slice(-1))}`;
}

/**
 * The 10-digit subscriber, no country prefix and no leading zero.
 *
 * ``+989121234567``, ``00989121234567``, ``09121234567`` and ``9121234567``
 * all fold to ``9121234567``, so the mask and the dialler agree on one form.
 */
function localForm(input: string): string {
  const digits = normalizePhone(input);
  return digits.replace(/^(?:\+?98|0098|0)/, '');
}

/** Local fold so this module never imports the whole utils barrel. */
function toPersian(value: string): string {
  const latin = '0123456789';
  const persian = '۰۱۲۳۴۵۶۷۸۹';
  return Array.from(value)
    .map((char) => {
      const index = latin.indexOf(char);
      return index === -1 ? char : persian[index];
    })
    .join('');
}
