export interface AddressEntry {
  id: number;
  user_id: number;
  label: string | null;
  full_name: string;
  phone: string;
  email: string | null;
  company_name: string | null;
  tax_id: string | null;
  country: string;
  city: string;
  address_line1: string;
  address_line2: string | null;
  postal_code: string | null;
  is_default: boolean;
  created_at: string;
}

export interface AddressEntryCreate {
  label?: string | null;
  full_name: string;
  phone: string;
  email?: string | null;
  company_name?: string | null;
  tax_id?: string | null;
  country: string;
  city: string;
  address_line1: string;
  address_line2?: string | null;
  postal_code?: string | null;
  is_default?: boolean;
}
