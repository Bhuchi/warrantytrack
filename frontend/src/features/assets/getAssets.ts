import type { AssetListItem, AssetListQuery, AssetListResponse } from "@/types/assetList";

/** Matches the API's default page size. */
export const PAGE_SIZE = 20;

/** Builds one mock row; the fields nobody filters on get fixed values. */
function asset(
  id: number,
  name: string,
  serial_number: string,
  category_name: string,
  vendor_name: string,
  location: string,
  warranty_status: AssetListItem["warranty_status"],
  warranty_end_date: string | null,
): AssetListItem {
  return {
    id: `mock-${id}`,
    name,
    serial_number,
    purchase_date: "2024-05-19",
    warranty_end_date,
    warranty_status,
    assigned_to_user_id: null,
    category_name,
    vendor_name,
    location,
  };
}

/**
 * 25 assets. The first seven are the rows in Figma D05 (3354:2), so the screen
 * can be compared with the design; the rest make a second page.
 */
const MOCK_ASSETS: AssetListItem[] = [
  asset(1, 'MacBook Pro 14"', "C02X1234ABC", "Laptop", "Apple", "IT Dept", "active", "2026-05-19"),
  asset(2, "Canon EOS R50", "CN2024-778120", "Camera", "Canon", "Marketing", "active", "2026-08-10"),
  asset(3, 'Dell Monitor 27"', "DM27-99213", "Monitor", "Dell", "IT Dept", "expiring_soon", "2026-05-21"),
  asset(4, "iPhone 15", "IP15-004512", "Mobile", "Apple", "Sales", "active", "2027-04-12"),
  asset(5, "HP Color LaserJet", "HP-LJ-30021", "Printer", "HP", "Admin", "expired", "2026-01-10"),
  asset(6, "Logitech MX Master 3S", "LG-MX3S-771", "Accessory", "Logitech", "IT Dept", "unknown", null),
  asset(7, "Dell XPS 15", "DX15-55021", "Laptop", "Dell", "Sales", "active", "2026-11-02"),
  asset(8, "Lenovo ThinkPad X1", "LN-X1-20481", "Laptop", "Lenovo", "IT Dept", "active", "2027-02-14"),
  asset(9, "Samsung Galaxy Tab S9", "SM-X710-3391", "Tablet", "Samsung", "Marketing", "expiring_soon", "2026-11-18"),
  asset(10, "Epson EcoTank L3250", "EP-L3250-118", "Printer", "Epson", "Admin", "active", "2027-06-30"),
  asset(11, "Sony WH-1000XM5", "SN-WH5-60412", "Accessory", "Sony", "Marketing", "expired", "2026-03-02"),
  asset(12, 'LG UltraFine 32"', "LG-32UN-8820", "Monitor", "LG", "IT Dept", "active", "2027-09-09"),
  asset(13, "iPad Air (M2)", "IPA-M2-55107", "Tablet", "Apple", "Sales", "active", "2027-03-21"),
  asset(14, "Cisco Catalyst 9200", "CS-9200-0042", "Network", "Cisco", "IT Dept", "unknown", null),
  asset(15, "Brother HL-L2350", "BR-L2350-771", "Printer", "Brother", "Admin", "expired", "2025-12-15"),
  asset(16, "ASUS ROG Zephyrus", "AS-ROG-90213", "Laptop", "ASUS", "Marketing", "active", "2027-01-08"),
  asset(17, "Dell OptiPlex 7010", "DO-7010-44518", "Desktop", "Dell", "Sales", "expiring_soon", "2026-11-25"),
  asset(18, "Logitech C920 Webcam", "LG-C920-1180", "Accessory", "Logitech", "IT Dept", "active", "2027-05-05"),
  asset(19, "Synology DS923+", "SY-923-77310", "Network", "Synology", "IT Dept", "active", "2028-02-01"),
  asset(20, "Canon imageRUNNER 2425", "CN-IR2425-09", "Printer", "Canon", "Admin", "active", "2027-07-19"),
  asset(21, "Apple Magic Keyboard", "AP-MK-33021", "Accessory", "Apple", "Sales", "unknown", null),
  asset(22, "HP EliteBook 840", "HP-EB840-6612", "Laptop", "HP", "Admin", "active", "2027-10-10"),
  asset(23, "Samsung Odyssey G7", "SM-G7-12093", "Monitor", "Samsung", "Marketing", "expired", "2026-02-28"),
  asset(24, "Google Pixel 8", "GP8-0040218", "Mobile", "Google", "Sales", "active", "2027-08-23"),
  asset(25, "Microsoft Surface Pro 9", "MS-SP9-48811", "Tablet", "Microsoft", "IT Dept", "expiring_soon", "2026-11-30"),
];

/** A short pause, so the screen's "loading" state is real while this is a mock. */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * One page of assets for the Assets List. The one place the screen gets them.
 *
 * Mock for now: filters MOCK_ASSETS the way the API will, after a short pause.
 * Search matches name and serial; the API also searches the invoice number,
 * which list rows do not include.
 *
 * TODO: when GET /assets exists (Leg A, Sirawich), replace the body with:
 *   return api.get<AssetListResponse>("/assets", { query: { ...query } });
 */
export async function getAssets(query: AssetListQuery = {}): Promise<AssetListResponse> {
  await delay(300);

  const search = (query.q ?? "").trim().toLowerCase();
  const page = query.page ?? 1;

  const matching = MOCK_ASSETS.filter(
    (item) =>
      (!query.status || item.warranty_status === query.status) &&
      (!search ||
        item.name.toLowerCase().includes(search) ||
        item.serial_number.toLowerCase().includes(search)),
  );

  const start = (page - 1) * PAGE_SIZE;

  return {
    items: matching.slice(start, start + PAGE_SIZE),
    total: matching.length,
    page,
    page_size: PAGE_SIZE,
  };
}
