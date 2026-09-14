
export function paiseToRupeesDisplay(paise: number): string {
  if (!Number.isInteger(paise)) {
    throw new TypeError(`paise must be an integer, got ${typeof paise}`);
  }

  const isNegative = paise < 0;
  const absPaise = Math.abs(paise);
  const wholeRupees = Math.floor(absPaise / 100);
  const remainderPaise = absPaise % 100;

  const sign = isNegative ? "-" : "";
  // Natively applies Indian grouping (e.g., 1,00,000)
  const grouped = wholeRupees.toLocaleString("en-IN");

  if (remainderPaise === 0) {
    return `${sign}\u20B9${grouped}`;
  }

  const paddedRemainder = remainderPaise.toString().padStart(2, "0");
  return `${sign}\u20B9${grouped}.${paddedRemainder}`;
}

export const formatPaiseToRupees = paiseToRupeesDisplay;