const persianNumberFormatter = new Intl.NumberFormat("fa-IR");
const persianPhoneFormatter = new Intl.NumberFormat("fa-IR", { useGrouping: false });

export function formatPersianNumber(value: number): string {
  return persianNumberFormatter.format(value);
}

export function formatPersianDigits(value: string | number): string {
  if (typeof value === "number") return persianPhoneFormatter.format(value);
  return value.replace(/[0-9]/g, (digit) => String.fromCharCode(0x06f0 + Number(digit)));
}
