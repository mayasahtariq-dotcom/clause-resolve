import type { VendorInput } from "../api/types";

export const nameKey = (name: string) => name.toLowerCase().replace(/[^a-z0-9]/g, "");

const DOMAIN_RE = /^(https?:\/\/)?(www\.)?([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}(\/\S*)?$/i;
const IP_RE = /^(https?:\/\/)?(\d{1,3}\.){3}\d{1,3}|\[[0-9a-f:]+\]/i;

/** Client-side checks for fast feedback. The API re-validates everything (including SSRF rules). */
export function validateVendor(input: VendorInput, existing: VendorInput[], max: number): string | null {
  const name = input.name.trim();
  if (!name) return "Enter a vendor name.";
  if (name.length > 120) return "Vendor names must be 120 characters or fewer.";
  if (!nameKey(name)) return "Vendor names need at least one letter or number.";
  if (existing.some((v) => nameKey(v.name) === nameKey(name))) return `${name} is already in the list.`;
  if (existing.length >= max) return `You can compare up to ${max} vendors at once.`;
  const domain = input.domain?.trim();
  if (domain) {
    if (IP_RE.test(domain)) return "Enter a domain name such as example.com, not an IP address.";
    if (/localhost|\.local\b|\.internal\b/i.test(domain)) return "Only public websites can be investigated.";
    if (!DOMAIN_RE.test(domain)) return "That doesn't look like a website domain (e.g. coursera.org).";
  }
  return null;
}
