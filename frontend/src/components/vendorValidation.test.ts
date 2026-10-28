import { validateVendor } from "./vendorValidation";

describe("validateVendor", () => {
  const existing = [{ name: "Coursera" }];
  it.each([
    [{ name: "" }, "Enter a vendor name."],
    [{ name: "  " }, "Enter a vendor name."],
    [{ name: "coursera" }, "coursera is already in the list."],
    [{ name: "Udemy", domain: "localhost" }, "Only public websites can be investigated."],
    [{ name: "Udemy", domain: "10.0.0.1" }, "Enter a domain name such as example.com, not an IP address."],
    [{ name: "Udemy", domain: "not a domain" }, "That doesn't look like a website domain (e.g. coursera.org)."],
    [{ name: "x".repeat(121) }, "Vendor names must be 120 characters or fewer."],
  ])("rejects %j", (input, message) => {
    expect(validateVendor(input, existing, 5)).toBe(message);
  });

  it("enforces the maximum", () => {
    expect(validateVendor({ name: "Six" }, Array.from({ length: 5 }, (_, i) => ({ name: `V${i}` })), 5)).toMatch(/up to 5/);
  });

  it.each(["udemy.com", "https://www.udemy.com/terms", "help.edx.org"])("accepts %s", (domain) => {
    expect(validateVendor({ name: "Udemy", domain }, existing, 5)).toBeNull();
  });
});
