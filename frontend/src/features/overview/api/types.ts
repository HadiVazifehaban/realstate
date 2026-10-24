/**
 * Statistics overview for the dashboard
 */

export interface OverviewStats {
  total_listings: number;
  showcase_buy: number;
  showcase_rent: number;
  radar_deals: number;
  new_today: number;
  trends: {
    total_listings: number;
    showcase_buy: number;
    showcase_rent: number;
    radar_deals: number;
  };
}

export interface AgencyStats {
  total_agencies: number;
  active_agencies: number;
  new_this_month: number;
  top_agencies: Array<{
    name: string;
    listings_count: number;
    city: string;
  }>;
}

export interface UserStats {
  total_users: number;
  active_brokers: number;
  new_this_month: number;
  top_brokers: Array<{
    name: string;
    listings_count: number;
    city: string;
  }>;
}

export interface RequestStats {
  total_requests: number;
  pending: number;
  completed: number;
  new_today: number;
}

export interface FinancialStats {
  revenue_this_month: number;
  revenue_this_year: number;
  trend_month: number;
}

export interface PropertyByCity {
  city: string;
  count: number;
}

export interface PropertyByType {
  type: string;
  count: number;
}

export interface PropertyByStatus {
  status: string;
  count: number;
}

export interface RecentActivity {
  id: string;
  type: 'new_listing' | 'radar_deal' | 'user_change' | 'new_agency' | 'new_request';
  title: string;
  description: string;
  timestamp: string;
  city?: string;
}

export interface FeaturedListing {
  id: string;
  title: string;
  price: number;
  city: string;
  type: string;
  status: string;
  views: number;
  image_url?: string;
}

export interface NewsItem {
  id: string;
  title: string;
  content: string;
  published_at: string;
  is_important: boolean;
}

export interface OverviewData {
  stats: OverviewStats;
  agency_stats: AgencyStats;
  user_stats: UserStats;
  request_stats: RequestStats;
  financial_stats: FinancialStats;
  by_city: PropertyByCity[];
  by_type: PropertyByType[];
  by_status: PropertyByStatus[];
  recent_activities: RecentActivity[];
  featured_listings: FeaturedListing[];
  news: NewsItem[];
}
