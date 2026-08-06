import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { 
  ShieldAlert, Shield, Trash2, Clock, Plus, History, Globe, Ban, 
  CheckCircle2, AlertCircle, Search, Eye, Lock, Unlock 
} from 'lucide-react';
import {
  fetchBlacklist, removeBlacklist, addBlacklistWithDuration, fetchBlockHistory,
  lookupGeoIP, fetchGeoAllow, fetchGeoWatch, addGeoAllow, removeGeoAllow,
  addGeoWatch, removeGeoWatch, fetchGeoBlocks, addGeoBlock, removeGeoBlock,
  fetchWhitelist, addWhitelist, removeWhitelist,
} from '../lib/api';
import { hasRole } from '../lib/auth';
import { formatDatetime } from '../lib/datetime';
import Pagination from '../components/Pagination';
import BlockIPModal from '../components/BlockIPModal';

const COMMON_COUNTRIES = [
  { code: 'CN', name: 'China' }, { code: 'RU', name: 'Russia' },
  { code: 'KP', name: 'North Korea' }, { code: 'IR', name: 'Iran' },
  { code: 'VN', name: 'Vietnam' }, { code: 'US', name: 'United States' },
  { code: 'DE', name: 'Germany' }, { code: 'FR', name: 'France' },
  { code: 'GB', name: 'United Kingdom' }, { code: 'CA', name: 'Canada' },
  { code: 'AU', name: 'Australia' }, { code: 'JP', name: 'Japan' },
  { code: 'KR', name: 'South Korea' }, { code: 'IN', name: 'India' },
  { code: 'BR', name: 'Brazil' }, { code: 'MX', name: 'Mexico' },
];

const ALL_COUNTRIES = [
  { value: 'AF', label: 'Afghanistan' }, { value: 'AL', label: 'Albania' },
  { value: 'DZ', label: 'Algeria' }, { value: 'AS', label: 'American Samoa' },
  { value: 'AD', label: 'Andorra' }, { value: 'AO', label: 'Angola' },
  { value: 'AI', label: 'Anguilla' }, { value: 'AQ', label: 'Antarctica' },
  { value: 'AG', label: 'Antigua and Barbuda' }, { value: 'AR', label: 'Argentina' },
  { value: 'AM', label: 'Armenia' }, { value: 'AW', label: 'Aruba' },
  { value: 'AU', label: 'Australia' }, { value: 'AT', label: 'Austria' },
  { value: 'AZ', label: 'Azerbaijan' }, { value: 'BS', label: 'Bahamas' },
  { value: 'BH', label: 'Bahrain' }, { value: 'BD', label: 'Bangladesh' },
  { value: 'BB', label: 'Barbados' }, { value: 'BY', label: 'Belarus' },
  { value: 'BE', label: 'Belgium' }, { value: 'BZ', label: 'Belize' },
  { value: 'BJ', label: 'Benin' }, { value: 'BM', label: 'Bermuda' },
  { value: 'BT', label: 'Bhutan' }, { value: 'BO', label: 'Bolivia' },
  { value: 'BA', label: 'Bosnia and Herzegovina' }, { value: 'BW', label: 'Botswana' },
  { value: 'BV', label: 'Bouvet Island' }, { value: 'BR', label: 'Brazil' },
  { value: 'IO', label: 'British Indian Ocean Territory' }, { value: 'BN', label: 'Brunei Darussalam' },
  { value: 'BG', label: 'Bulgaria' }, { value: 'BF', label: 'Burkina Faso' },
  { value: 'BI', label: 'Burundi' }, { value: 'KH', label: 'Cambodia' },
  { value: 'CM', label: 'Cameroon' }, { value: 'CA', label: 'Canada' },
  { value: 'CV', label: 'Cape Verde' }, { value: 'KY', label: 'Cayman Islands' },
  { value: 'CF', label: 'Central African Republic' }, { value: 'TD', label: 'Chad' },
  { value: 'CL', label: 'Chile' }, { value: 'CN', label: 'China' },
  { value: 'CX', label: 'Christmas Island' }, { value: 'CC', label: 'Cocos (Keeling) Islands' },
  { value: 'CO', label: 'Colombia' }, { value: 'KM', label: 'Comoros' },
  { value: 'CG', label: 'Congo' }, { value: 'CD', label: 'Congo, The Democratic Republic of the' },
  { value: 'CK', label: 'Cook Islands' }, { value: 'CR', label: 'Costa Rica' },
  { value: 'CI', label: 'Cote D\'Ivoire' }, { value: 'HR', label: 'Croatia' },
  { value: 'CU', label: 'Cuba' }, { value: 'CY', label: 'Cyprus' },
  { value: 'CZ', label: 'Czech Republic' }, { value: 'DK', label: 'Denmark' },
  { value: 'DJ', label: 'Djibouti' }, { value: 'DM', label: 'Dominica' },
  { value: 'DO', label: 'Dominican Republic' }, { value: 'EC', label: 'Ecuador' },
  { value: 'EG', label: 'Egypt' }, { value: 'SV', label: 'El Salvador' },
  { value: 'GQ', label: 'Equatorial Guinea' }, { value: 'ER', label: 'Eritrea' },
  { value: 'EE', label: 'Estonia' }, { value: 'ET', label: 'Ethiopia' },
  { value: 'FK', label: 'Falkland Islands (Malvinas)' }, { value: 'FO', label: 'Faroe Islands' },
  { value: 'FJ', label: 'Fiji' }, { value: 'FI', label: 'Finland' },
  { value: 'FR', label: 'France' }, { value: 'GF', label: 'French Guiana' },
  { value: 'PF', label: 'French Polynesia' }, { value: 'TF', label: 'French Southern Territories' },
  { value: 'GA', label: 'Gabon' }, { value: 'GM', label: 'Gambia' },
  { value: 'GE', label: 'Georgia' }, { value: 'DE', label: 'Germany' },
  { value: 'GH', label: 'Ghana' }, { value: 'GI', label: 'Gibraltar' },
  { value: 'GR', label: 'Greece' }, { value: 'GL', label: 'Greenland' },
  { value: 'GD', label: 'Grenada' }, { value: 'GP', label: 'Guadeloupe' },
  { value: 'GU', label: 'Guam' }, { value: 'GT', label: 'Guatemala' },
  { value: 'GN', label: 'Guinea' }, { value: 'GW', label: 'Guinea-Bissau' },
  { value: 'GY', label: 'Guyana' }, { value: 'HT', label: 'Haiti' },
  { value: 'HM', label: 'Heard Island and Mcdonald Islands' }, { value: 'VA', label: 'Holy See (Vatican City State)' },
  { value: 'HN', label: 'Honduras' }, { value: 'HK', label: 'Hong Kong' },
  { value: 'HU', label: 'Hungary' }, { value: 'IS', label: 'Iceland' },
  { value: 'IN', label: 'India' }, { value: 'ID', label: 'Indonesia' },
  { value: 'IR', label: 'Iran, Islamic Republic Of' }, { value: 'IQ', label: 'Iraq' },
  { value: 'IE', label: 'Ireland' }, { value: 'IL', label: 'Israel' },
  { value: 'IT', label: 'Italy' }, { value: 'JM', label: 'Jamaica' },
  { value: 'JP', label: 'Japan' }, { value: 'JO', label: 'Jordan' },
  { value: 'KZ', label: 'Kazakhstan' }, { value: 'KE', label: 'Kenya' },
  { value: 'KI', label: 'Kiribati' }, { value: 'KP', label: 'Korea, Democratic People\'s Republic of' },
  { value: 'KR', label: 'Korea, Republic of' }, { value: 'KW', label: 'Kuwait' },
  { value: 'KG', label: 'Kyrgyzstan' }, { value: 'LA', label: 'Lao People\'s Democratic Republic of' },
  { value: 'LV', label: 'Latvia' }, { value: 'LB', label: 'Lebanon' },
  { value: 'LS', label: 'Lesotho' }, { value: 'LR', label: 'Liberia' },
  { value: 'LY', label: 'Libyan Arab Jamahiriya' }, { value: 'LI', label: 'Liechtenstein' },
  { value: 'LT', label: 'Lithuania' }, { value: 'LU', label: 'Luxembourg' },
  { value: 'MO', label: 'Macao' }, { value: 'MK', label: 'Macedonia, The Former Yugoslav Republic of' },
  { value: 'MG', label: 'Madagascar' }, { value: 'MW', label: 'Malawi' },
  { value: 'MY', label: 'Malaysia' }, { value: 'MV', label: 'Maldives' },
  { value: 'ML', label: 'Mali' }, { value: 'MT', label: 'Malta' },
  { value: 'MH', label: 'Marshall Islands' }, { value: 'MQ', label: 'Martinique' },
  { value: 'MR', label: 'Mauritania' }, { value: 'MU', label: 'Mauritius' },
  { value: 'YT', label: 'Mayotte' }, { value: 'MX', label: 'Mexico' },
  { value: 'FM', label: 'Micronesia, Federated States of' }, { value: 'MD', label: 'Moldova, Republic of' },
  { value: 'MC', label: 'Monaco' }, { value: 'MN', label: 'Mongolia' },
  { value: 'MS', label: 'Montserrat' }, { value: 'MA', label: 'Morocco' },
  { value: 'MZ', label: 'Mozambique' }, { value: 'MM', label: 'Myanmar' },
  { value: 'NA', label: 'Namibia' }, { value: 'NR', label: 'Nauru' },
  { value: 'NP', label: 'Nepal' }, { value: 'NL', label: 'Netherlands' },
  { value: 'AN', label: 'Netherlands Antilles' }, { value: 'NC', label: 'New Caledonia' },
  { value: 'NZ', label: 'New Zealand' }, { value: 'NI', label: 'Nicaragua' },
  { value: 'NE', label: 'Niger' }, { value: 'NG', label: 'Nigeria' },
  { value: 'NU', label: 'Niue' }, { value: 'NF', label: 'Norfolk Island' },
  { value: 'MP', label: 'Northern Mariana Islands' }, { value: 'NO', label: 'Norway' },
  { value: 'OM', label: 'Oman' }, { value: 'PK', label: 'Pakistan' },
  { value: 'PW', label: 'Palau' }, { value: 'PS', label: 'Palestinian Territory, Occupied' },
  { value: 'PA', label: 'Panama' }, { value: 'PG', label: 'Papua New Guinea' },
  { value: 'PY', label: 'Paraguay' }, { value: 'PE', label: 'Peru' },
  { value: 'PH', label: 'Philippines' }, { value: 'PN', label: 'Pitcairn' },
  { value: 'PL', label: 'Poland' }, { value: 'PT', label: 'Portugal' },
  { value: 'PR', label: 'Puerto Rico' }, { value: 'QA', label: 'Qatar' },
  { value: 'RE', label: 'Reunion' }, { value: 'RO', label: 'Romania' },
  { value: 'RU', label: 'Russian Federation' }, { value: 'RW', label: 'Rwanda' },
  { value: 'SH', label: 'Saint Helena' }, { value: 'KN', label: 'Saint Kitts and Nevis' },
  { value: 'LC', label: 'Saint Lucia' }, { value: 'PM', label: 'Saint Pierre and Miquelon' },
  { value: 'VC', label: 'Saint Vincent and The Grenadines' }, { value: 'WS', label: 'Samoa' },
  { value: 'SM', label: 'San Marino' }, { value: 'ST', label: 'Sao Tome and Principe' },
  { value: 'SA', label: 'Saudi Arabia' }, { value: 'SN', label: 'Senegal' },
  { value: 'CS', label: 'Serbia and Montenegro' }, { value: 'SC', label: 'Seychelles' },
  { value: 'SL', label: 'Sierra Leone' }, { value: 'SG', label: 'Singapore' },
  { value: 'SK', label: 'Slovakia' }, { value: 'SI', label: 'Slovenia' },
  { value: 'SB', label: 'Solomon Islands' }, { value: 'SO', label: 'Somalia' },
  { value: 'ZA', label: 'South Africa' }, { value: 'GS', label: 'South Georgia and The South Sandwich Islands' },
  { value: 'ES', label: 'Spain' }, { value: 'LK', label: 'Sri Lanka' },
  { value: 'SD', label: 'Sudan' }, { value: 'SR', label: 'Suriname' },
  { value: 'SJ', label: 'Svalbard and Jan Mayen' }, { value: 'SZ', label: 'Swaziland' },
  { value: 'SE', label: 'Sweden' }, { value: 'CH', label: 'Switzerland' },
  { value: 'SY', label: 'Syrian Arab Republic' }, { value: 'TW', label: 'Taiwan, Province of China' },
  { value: 'TJ', label: 'Tajikistan' }, { value: 'TZ', label: 'Tanzania, United Republic of' },
  { value: 'TH', label: 'Thailand' }, { value: 'TL', label: 'Timor-Leste' },
  { value: 'TG', label: 'Togo' }, { value: 'TK', label: 'Tokelau' },
  { value: 'TO', label: 'Tonga' }, { value: 'TT', label: 'Trinidad and Tobago' },
  { value: 'TN', label: 'Tunisia' }, { value: 'TR', label: 'Turkey' },
  { value: 'TM', label: 'Turkmenistan' }, { value: 'TC', label: 'Turks and Caicos Islands' },
  { value: 'TV', label: 'Tuvalu' }, { value: 'UG', label: 'Uganda' },
  { value: 'UA', label: 'Ukraine' }, { value: 'AE', label: 'United Arab Emirates' },
  { value: 'GB', label: 'United Kingdom' }, { value: 'US', label: 'United States' },
  { value: 'UM', label: 'United States Minor Outlying Islands' }, { value: 'UY', label: 'Uruguay' },
  { value: 'UZ', label: 'Uzbekistan' }, { value: 'VU', label: 'Vanuatu' },
  { value: 'VE', label: 'Venezuela' }, { value: 'VN', label: 'Viet Nam' },
  { value: 'VG', label: 'Virgin Islands, British' }, { value: 'VI', label: 'Virgin Islands, U.S.' },
  { value: 'WF', label: 'Wallis and Futuna' }, { value: 'EH', label: 'Western Sahara' },
  { value: 'YE', label: 'Yemen' }, { value: 'ZM', label: 'Zambia' },
  { value: 'ZW', label: 'Zimbabwe' }
];

export default function Firewall() {
  const [tab, setTab] = useState('active'); // active, history, geo-blocking, whitelist

  // IP Blacklist state
  const [blacklist, setBlacklist] = useState([]);
  const [history, setHistory] = useState([]);
  const [showBlockIPModal, setShowBlockIPModal] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalBlacklist, setTotalBlacklist] = useState(0);
  const [totalHistory, setTotalHistory] = useState(0);

  // Whitelist state
  const [whitelist, setWhitelist] = useState([]);
  const [newWlIp, setNewWlIp] = useState('');
  const [newWlReason, setNewWlReason] = useState('');
  const [wlLoading, setWlLoading] = useState(false);
  const [wlMessage, setWlMessage] = useState({ type: '', text: '' });

  const flashWlMessage = useCallback((type, text) => {
    setWlMessage({ type, text });
    setTimeout(() => setWlMessage({ type: '', text: '' }), 3000);
  }, []);

  const loadWhitelist = useCallback(async () => {
    try {
      const res = await fetchWhitelist();
      setWhitelist(res.data?.items || res.items || res.data || []);
    } catch { }
  }, []);

  const handleAddWhitelist = async () => {
    if (!newWlIp.trim()) return;
    setWlLoading(true);
    try {
      await addWhitelist({ ip_address: newWlIp.trim(), reason: newWlReason || 'Added from Firewall' });
      setNewWlIp(''); setNewWlReason('');
      loadWhitelist();
      flashWlMessage('success', `Đã thêm ${newWlIp} vào whitelist`);
    } catch (err) {
      flashWlMessage('error', err.response?.data?.message || err.response?.data?.detail || 'Không thể thêm IP');
    }
    setWlLoading(false);
  };

  const handleRemoveWhitelist = async (id, ip) => {
    if (!window.confirm(`Xóa ${ip} khỏi whitelist?`)) return;
    try {
      await removeWhitelist({ whitelist_id: id });
      loadWhitelist();
      flashWlMessage('success', `Đã xóa ${ip} khỏi whitelist`);
    } catch (err) {
      flashWlMessage('error', err.response?.data?.detail || 'Không thể xóa IP');
    }
  };

  // Geo Blocking state
  const [geoRules, setGeoRules] = useState([]);
  const [allowRules, setAllowRules] = useState([]);
  const [watchRules, setWatchRules] = useState([]);
  const [lookupIp, setLookupIp] = useState('');
  const [lookupResult, setLookupResult] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [geoMessage, setGeoMessage] = useState({ type: '', text: '' });
  const [geoLoading, setGeoLoading] = useState(false);

  const flashGeoMessage = useCallback((type, text) => {
    setGeoMessage({ type, text });
    setTimeout(() => setGeoMessage({ type: '', text: '' }), 3000);
  }, []);

  // IP Blacklist functions
  const loadBlacklist = async () => {
    try {
      const data = await fetchBlacklist({ limit: pageSize, skip: (currentPage - 1) * pageSize });
      setBlacklist(Array.isArray(data.items) ? data.items : (Array.isArray(data) ? data : []));
      setTotalBlacklist(data.total || data.length || 0);
    } catch (err) {
      console.error('Failed to fetch blacklist:', err);
    }
  };

  const loadHistory = async () => {
    try {
      const data = await fetchBlockHistory({ limit: pageSize, skip: (currentPage - 1) * pageSize });
      setHistory(Array.isArray(data.items) ? data.items : (Array.isArray(data) ? data : []));
      setTotalHistory(data.total || data.length || 0);
    } catch (err) {
      console.error('Failed to fetch block history:', err);
    }
  };

  const handleUnblock = async (ip) => {
    if (window.confirm(`Bạn có chắc muốn gỡ chặn IP ${ip}?`)) {
      try {
        await removeBlacklist(ip);
        loadBlacklist();
        loadHistory();
      } catch (err) {
        setError(`Không thể gỡ chặn IP ${ip}: ${err.response?.data?.detail || err.message}`);
      }
    }
  };

  const handleAddBlock = async (data) => {
    setError('');
    setLoading(true);
    try {
      await addBlacklistWithDuration(data.ip_address, data.reason || 'Manual block', data.expires_hours || 24);
      loadBlacklist();
      loadHistory();
      setShowBlockIPModal(false);
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể thêm IP vào blacklist');
    } finally {
      setLoading(false);
    }
  };

  // Geo Blocking functions
  const loadGeoBlocks = useCallback(async () => {
    setGeoLoading(true);
    try {
      const data = await fetchGeoBlocks();
      setGeoRules(Array.isArray(data) ? data : []);
    } catch (err) {
      flashGeoMessage('error', 'Không thể tải quy tắc Geo Blocking: ' + (err.response?.data?.detail || err.message));
    } finally {
      setGeoLoading(false);
    }
  }, [flashGeoMessage]);

  const getCountryStatus = useCallback((countryCode) => {
    const isBlocked = geoRules.some(r => r.country_code === countryCode && r.is_active);
    const isAllowed = allowRules.some(r => r.country_code === countryCode);
    const isWatched = watchRules.some(r => r.country_code === countryCode);
    return { isBlocked, isAllowed, isWatched };
  }, [geoRules, allowRules, watchRules]);

  const handleCountryAction = useCallback(async (countryCode, countryName, action) => {
    if (!hasRole(['admin'])) {
      flashGeoMessage('error', 'Bạn không có quyền thực hiện thao tác này.');
      return;
    }

    const finalCountryName = countryName || countryCode;

    try {
      if (action === 'block') {
        await addGeoBlock({ country_code: countryCode, country_name: finalCountryName });
        flashGeoMessage('success', `Đã chặn truy cập từ ${finalCountryName}.`);
        setGeoRules(prev => [...prev, { country_code: countryCode, country_name: finalCountryName, is_active: true }]);
      } else if (action === 'allow') {
        await addGeoAllow({ country_code: countryCode, country_name: finalCountryName });
        flashGeoMessage('success', `Đã cho phép truy cập từ ${finalCountryName}.`);
        fetchGeoAllow().then(setAllowRules);
      } else if (action === 'watch') {
        await addGeoWatch({ country_code: countryCode, country_name: finalCountryName });
        flashGeoMessage('success', `Đã thêm ${finalCountryName} vào danh sách theo dõi.`);
        fetchGeoWatch().then(setWatchRules);
      } else if (action === 'unblock') {
        await removeGeoBlock(countryCode);
        flashGeoMessage('success', `Đã gỡ chặn ${finalCountryName}.`);
        setGeoRules(prev => prev.filter(r => r.country_code !== countryCode));
      } else if (action === 'unallow') {
        await removeGeoAllow(countryCode);
        flashGeoMessage('success', `Đã gỡ cho phép ${finalCountryName}.`);
        fetchGeoAllow().then(setAllowRules);
      } else if (action === 'unwatch') {
        await removeGeoWatch(countryCode);
        flashGeoMessage('success', `Đã gỡ theo dõi ${finalCountryName}.`);
        fetchGeoWatch().then(setWatchRules);
      }
    } catch (err) {
      flashGeoMessage('error', 'Lỗi khi thực hiện thao tác: ' + (err.response?.data?.detail || err.message));
      loadGeoBlocks();
    }
  }, [flashGeoMessage, loadGeoBlocks]);

  const filteredCountries = useMemo(() => 
    ALL_COUNTRIES.filter(c =>
      c.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.value.toLowerCase().includes(searchQuery.toLowerCase())
    ), [searchQuery]
  );

  const allCountriesWithStatus = useMemo(() => 
    ALL_COUNTRIES.map(c => ({
      ...c,
      status: getCountryStatus(c.value)
    })).filter(c => c.status.isBlocked || c.status.isAllowed || c.status.isWatched),
    [getCountryStatus]
  );

  // Trigger loading data on tab or page change
  useEffect(() => {
    if (tab === 'active' || tab === 'history') {
      loadBlacklist();
      loadHistory();
    } else if (tab === 'geo-blocking') {
      if (hasRole(['admin'])) {
        loadGeoBlocks();
        fetchGeoAllow().then(setAllowRules).catch(() => {});
        fetchGeoWatch().then(setWatchRules).catch(() => {});
      }
    } else if (tab === 'whitelist') {
      loadWhitelist();
    }
  }, [currentPage, pageSize, tab, loadGeoBlocks, loadWhitelist]);

  const handleLookup = async () => {
    if (!lookupIp.trim()) return;
    try {
      const result = await lookupGeoIP(lookupIp.trim());
      setLookupResult(result);
    } catch (err) {
      flashGeoMessage('error', 'Không tra cứu được IP');
    }
  };

  const canManage = hasRole(['admin', 'security_analyst']);
  const canManageGeo = hasRole(['admin']);

  const thClass = "text-left px-4 py-3 font-medium text-slate-400 text-xs uppercase tracking-wider";
  const tdClass = "px-4 py-3 text-sm";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/20">
          <ShieldAlert className="w-6 h-6 text-red-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Quản lý Tường lửa</h1>
          <p className="text-sm text-slate-500 mt-0.5">Cấu hình IP Blacklist, Whitelist và Chặn Quốc gia (Geo Blocking)</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg px-4 py-3 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')} className="ml-3 underline text-xs hover:text-red-300">Đóng</button>
        </div>
      )}

      {/* Toast Notification for Geo-blocking */}
      {geoMessage.text && (
        <div className={`fixed top-4 right-4 p-4 rounded-xl shadow-2xl flex items-center gap-3 z-50 border bg-slate-900 ${
          geoMessage.type === 'success'
            ? 'border-emerald-500/30 text-emerald-400'
            : 'border-red-500/30 text-red-400'
        }`}>
          {geoMessage.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          <span className="text-sm font-medium">{geoMessage.text}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-800/40 p-1 rounded-lg w-fit border border-slate-700/40">
        {[
          { id: 'active', label: 'IP Đang chặn', count: totalBlacklist },
          { id: 'history', label: 'Lịch sử block IP', icon: History },
          { id: 'geo-blocking', label: 'Chặn Quốc gia (Geo)', icon: Globe },
          { id: 'whitelist', label: 'Whitelist', icon: Shield },
        ].map(({ id, label, icon: Icon, count }) => (
          <button
            key={id}
            type="button"
            onClick={() => { setTab(id); setCurrentPage(1); }}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-md transition-all ${
              tab === id
                ? 'bg-slate-700 text-slate-100 shadow-sm'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            {Icon && <Icon className="w-4 h-4" />}
            {label}
            {count != null && tab === 'active' && id === 'active' && count > 0 && (
              <span className="bg-red-500/20 text-red-400 text-xs px-1.5 py-0.5 rounded-full border border-red-500/20">{count}</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab: Active Blocked IPs */}
      {tab === 'active' && (
        <>
          {canManage && (
            <div className="bg-slate-900/60 backdrop-blur-sm border border-slate-800/60 rounded-xl p-4 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-slate-200">Chặn IP thủ công</h2>
                <p className="text-xs text-slate-500 mt-0.5">Thêm IP vào blacklist toàn cục với thời gian tùy chọn</p>
              </div>
              <button
                onClick={() => setShowBlockIPModal(true)}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-sm font-medium transition-colors shadow-lg shadow-red-500/20"
              >
                <Plus className="w-4 h-4" /> Chặn IP
              </button>
            </div>
          )}

          <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 overflow-hidden">
            <div className="overflow-auto max-h-[calc(100vh-380px)]">
              <table className="w-full text-left">
                <thead className="bg-slate-800/80 border-b border-slate-700/60 sticky top-0">
                  <tr>
                    <th className={thClass}>IP</th>
                    <th className={thClass}>Lý do</th>
                    <th className={thClass}>Thời gian chặn</th>
                    <th className={thClass}>Hết hạn</th>
                    {canManage && <th className={`${thClass} text-right`}>Thao tác</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {blacklist.length === 0 ? (
                    <tr><td colSpan={5} className="px-4 py-10 text-center text-slate-600">Không có IP bị chặn</td></tr>
                  ) : blacklist.map((item) => (
                    <tr key={item.ip_address} className="hover:bg-slate-800/40 transition-colors">
                      <td className={`${tdClass} font-mono text-blue-400`}>{item.ip_address}</td>
                      <td className={`${tdClass} text-slate-400`}>{item.reason || '—'}</td>
                      <td className={`${tdClass} text-slate-500 text-xs`}>{formatDatetime(item.created_at)}</td>
                      <td className={`${tdClass} text-xs`}>
                        <span className={`flex items-center gap-1 ${item.expires_at ? 'text-amber-400' : 'text-red-400'}`}>
                          <Clock className="w-3 h-3" />
                          {item.expires_at ? formatDatetime(item.expires_at) : 'Vĩnh viễn'}
                        </span>
                      </td>
                      {canManage && (
                        <td className={`${tdClass} text-right`}>
                          <button type="button" onClick={() => handleUnblock(item.ip_address)}
                            className="p-1.5 bg-red-500/10 text-red-400 hover:bg-red-500/20 rounded border border-red-500/20 transition-colors">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              currentPage={currentPage}
              totalPages={Math.ceil(totalBlacklist / pageSize)}
              onPageChange={setCurrentPage}
              pageSize={pageSize}
              onPageSizeChange={(newSize) => { setPageSize(newSize); setCurrentPage(1) }}
            />
          </div>
        </>
      )}

      {/* Tab: Firewall Block History */}
      {tab === 'history' && (
        <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 overflow-hidden">
          <div className="overflow-auto max-h-[calc(100vh-380px)]">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-800/80 border-b border-slate-700/60 sticky top-0">
                <tr>
                  <th className={thClass}>Thời gian</th>
                  <th className={thClass}>IP</th>
                  <th className={thClass}>Hành động</th>
                  <th className={thClass}>Thời hạn</th>
                  <th className={thClass}>Lý do</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {history.length === 0 ? (
                  <tr><td colSpan={5} className="px-4 py-10 text-center text-slate-600">Không có lịch sử tác vụ chặn</td></tr>
                ) : history.map((h) => (
                  <tr key={h.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className={`${tdClass} text-slate-500 text-xs`}>{formatDatetime(h.created_at)}</td>
                    <td className={`${tdClass} font-mono text-blue-400`}>{h.ip_address}</td>
                    <td className={tdClass}>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${h.action === 'block' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'}`}>
                        {h.action}
                      </span>
                    </td>
                    <td className={`${tdClass} text-slate-400`}>{h.duration_hours ? `${h.duration_hours}h` : h.action === 'block' ? '∞' : '—'}</td>
                    <td className={`${tdClass} text-slate-500`}>{h.reason || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            currentPage={currentPage}
            totalPages={Math.ceil(totalHistory / pageSize)}
            onPageChange={setCurrentPage}
            pageSize={pageSize}
            onPageSizeChange={(newSize) => { setPageSize(newSize); setCurrentPage(1) }}
          />
        </div>
      )}

      {/* Tab: Geo Blocking */}
      {tab === 'geo-blocking' && (
        <>
          {!canManageGeo ? (
            <div className="flex flex-col items-center justify-center h-64 text-center">
              <AlertCircle className="w-12 h-12 text-red-400 mb-3" />
              <p className="text-xl font-semibold text-slate-200">Truy cập bị từ chối</p>
              <p className="text-slate-500 mt-1">Chỉ quản trị viên cấp cao (Admin) mới có quyền truy cập Geo Blocking.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* IP Lookup Section */}
              <div className="bg-slate-900/60 backdrop-blur-sm p-4 rounded-xl border border-slate-800/60">
                <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                  <Search className="w-4 h-4 text-blue-400" /> Tra cứu quốc gia từ IP
                </h2>
                <div className="flex gap-2">
                  <input
                    value={lookupIp}
                    onChange={(e) => setLookupIp(e.target.value)}
                    placeholder="185.221.20.10"
                    className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 font-mono text-sm focus:outline-none focus:border-blue-500 transition-colors"
                  />
                  <button type="button" onClick={handleLookup} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white text-sm transition-colors">Tra cứu</button>
                </div>
                {lookupResult && (
                  <div className="mt-3 p-3 bg-slate-800/50 rounded-lg border border-slate-700/40">
                    <p className="text-sm text-slate-400 mb-2">
                      <span className="font-mono text-blue-400">{lookupResult.ip}</span>
                      {' → '}
                      <strong className="text-slate-200">{lookupResult.country_name || 'Unknown'}</strong>
                      {lookupResult.country_code && ` (${lookupResult.country_code})`}
                    </p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleCountryAction(lookupResult.country_code, lookupResult.country_name, 'block')}
                        className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs rounded-lg flex items-center gap-1 transition-colors"
                      >
                        <Ban className="w-3 h-3" /> Chặn
                      </button>
                      <button
                        onClick={() => handleCountryAction(lookupResult.country_code, lookupResult.country_name, 'allow')}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs rounded-lg flex items-center gap-1 transition-colors"
                      >
                        <CheckCircle2 className="w-3 h-3" /> Cho phép
                      </button>
                      <button
                        onClick={() => handleCountryAction(lookupResult.country_code, lookupResult.country_name, 'watch')}
                        className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white text-xs rounded-lg flex items-center gap-1 transition-colors"
                      >
                        <Eye className="w-3 h-3" /> Theo dõi
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Common Countries Quick Block Section */}
              <div className="bg-slate-900/60 backdrop-blur-sm p-4 rounded-xl border border-slate-800/60">
                <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                  <Ban className="w-4 h-4 text-violet-400" /> Chặn nhanh các quốc gia phổ biến
                </h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                  {COMMON_COUNTRIES.map((c) => {
                    const status = getCountryStatus(c.code);
                    return (
                      <button
                        key={c.code}
                        onClick={() => handleCountryAction(c.code, c.name, status.isBlocked ? 'unblock' : 'block')}
                        disabled={geoLoading || !hasRole(['admin'])}
                        className={`px-3 py-2 text-xs rounded-lg border font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-1 ${
                          status.isBlocked
                            ? 'bg-violet-600 text-white border-violet-600 shadow-lg shadow-violet-500/20'
                            : 'bg-slate-800/50 text-slate-400 border-slate-700 hover:border-violet-500/50 hover:text-slate-200'
                        }`}
                      >
                        {status.isBlocked && <CheckCircle2 className="w-3 h-3 flex-shrink-0" />}
                        <span className="truncate">{c.code} — {c.name}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Country Search Section */}
              <div className="bg-slate-900/60 backdrop-blur-sm p-4 rounded-xl border border-slate-800/60">
                <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                  <Globe className="w-4 h-4 text-violet-400" /> Tìm kiếm quốc gia
                </h2>
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Nhập tên quốc gia hoặc mã quốc gia..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 text-sm focus:outline-none focus:border-blue-500 transition-colors"
                />
                {searchQuery && filteredCountries.length > 0 && (
                  <div className="mt-3 max-h-48 overflow-auto border border-slate-700/60 rounded-lg bg-slate-800/40">
                    {filteredCountries.slice(0, 20).map((c) => {
                      const status = getCountryStatus(c.value);
                      const countryName = c.label;
                      return (
                        <div key={c.value} className="flex items-center justify-between p-2.5 hover:bg-slate-700/40 border-b border-slate-700/40 last:border-0 transition-colors">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium text-slate-200 text-sm">{c.label}</span>
                            <span className="text-xs text-slate-500">({c.value})</span>
                            {status.isBlocked && <span className="px-1.5 py-0.5 bg-red-500/10 text-red-400 border border-red-500/20 text-xs rounded-full">Đã chặn</span>}
                            {status.isAllowed && <span className="px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs rounded-full">Đã cho phép</span>}
                            {status.isWatched && <span className="px-1.5 py-0.5 bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs rounded-full">Đang theo dõi</span>}
                          </div>
                          <div className="flex gap-1 flex-shrink-0">
                            <button
                              onClick={() => handleCountryAction(c.value, countryName, status.isBlocked ? 'unblock' : 'block')}
                              className={`px-2 py-1 text-xs rounded transition-colors ${
                                status.isBlocked ? 'bg-slate-700 text-slate-400 hover:bg-slate-600' : 'bg-red-600 text-white hover:bg-red-500'
                              }`}
                            >
                              {status.isBlocked ? 'Gỡ chặn' : 'Chặn'}
                            </button>
                            <button
                              onClick={() => handleCountryAction(c.value, countryName, status.isAllowed ? 'unallow' : 'allow')}
                              className={`px-2 py-1 text-xs rounded transition-colors ${
                                status.isAllowed ? 'bg-slate-700 text-slate-400 hover:bg-slate-600' : 'bg-emerald-600 text-white hover:bg-emerald-500'
                              }`}
                            >
                              {status.isAllowed ? 'Gỡ cho phép' : 'Cho phép'}
                            </button>
                            <button
                              onClick={() => handleCountryAction(c.value, countryName, status.isWatched ? 'unwatch' : 'watch')}
                              disabled={status.isBlocked || status.isAllowed}
                              className={`px-2 py-1 text-xs rounded transition-colors ${
                                status.isWatched ? 'bg-slate-700 text-slate-400' : 'bg-amber-600 text-white hover:bg-amber-500'
                              } disabled:opacity-50 disabled:cursor-not-allowed`}
                            >
                              {status.isWatched ? 'Gỡ theo dõi' : 'Theo dõi'}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
                {searchQuery && filteredCountries.length === 0 && (
                  <p className="mt-3 text-sm text-slate-600">Không tìm thấy quốc gia nào.</p>
                )}
              </div>

              {/* Active Rules Section */}
              <div className="bg-slate-900/60 backdrop-blur-sm p-4 rounded-xl border border-slate-800/60">
                <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                  <Shield className="w-4 h-4 text-violet-400" /> Các quốc gia đang có quy tắc ({allCountriesWithStatus.length})
                </h2>
                {geoLoading ? (
                  <p className="text-slate-500 text-sm">Đang tải...</p>
                ) : allCountriesWithStatus.length > 0 ? (
                  <div className="overflow-auto max-h-96 rounded-lg border border-slate-700/40">
                    <table className="w-full text-sm">
                      <thead className="bg-slate-800/80 border-b border-slate-700/60 text-slate-400 text-xs uppercase tracking-wider sticky top-0">
                        <tr>
                          <th className="px-4 py-3 text-left">Quốc gia</th>
                          <th className="px-4 py-3 text-left">Mã</th>
                          <th className="px-4 py-3 text-left">Trạng thái</th>
                          <th className="px-4 py-3 text-right">Thao tác</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {allCountriesWithStatus.map((c) => {
                          const countryName = c.label;
                          return (
                            <tr key={c.value} className="hover:bg-slate-800/40 transition-colors">
                              <td className="px-4 py-3 font-medium text-slate-200">{c.label}</td>
                              <td className="px-4 py-3 text-slate-400 font-mono text-xs">{c.value}</td>
                              <td className="px-4 py-3">
                                <div className="flex gap-1 flex-wrap">
                                  {c.status.isBlocked && (
                                    <span className="px-2 py-0.5 bg-red-500/10 text-red-400 border border-red-500/20 text-xs rounded-full flex items-center gap-1">
                                      <Lock className="w-3 h-3" /> Đã chặn
                                    </span>
                                  )}
                                  {c.status.isAllowed && (
                                    <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs rounded-full flex items-center gap-1">
                                      <Unlock className="w-3 h-3" /> Đã cho phép
                                    </span>
                                  )}
                                  {c.status.isWatched && (
                                    <span className="px-2 py-0.5 bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs rounded-full flex items-center gap-1">
                                      <Eye className="w-3 h-3" /> Đang theo dõi
                                    </span>
                                  )}
                                </div>
                              </td>
                              <td className="px-4 py-3 text-right">
                                <div className="flex justify-end gap-1">
                                  {c.status.isBlocked && (
                                    <button
                                      onClick={() => handleCountryAction(c.value, countryName, 'unblock')}
                                      className="px-2 py-1 bg-slate-700 text-slate-400 text-xs rounded hover:bg-slate-600 transition-colors"
                                    >
                                      Gỡ chặn
                                    </button>
                                  )}
                                  {c.status.isAllowed && (
                                    <button
                                      onClick={() => handleCountryAction(c.value, countryName, 'unallow')}
                                      className="px-2 py-1 bg-slate-700 text-slate-400 text-xs rounded hover:bg-slate-600 transition-colors"
                                    >
                                      Gỡ cho phép
                                    </button>
                                  )}
                                  {c.status.isWatched && (
                                    <button
                                      onClick={() => handleCountryAction(c.value, countryName, 'unwatch')}
                                      className="px-2 py-1 bg-slate-700 text-slate-400 text-xs rounded hover:bg-slate-600 transition-colors"
                                    >
                                      Gỡ theo dõi
                                    </button>
                                  )}
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-slate-600 text-sm">Chưa có quốc gia nào có quy tắc.</p>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* Tab: Whitelist */}
      {tab === 'whitelist' && (
        <div className="space-y-4">
          {/* Toast */}
          {wlMessage.text && (
            <div className={`p-3 rounded-lg text-sm flex items-center gap-2 border ${
              wlMessage.type === 'success'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : 'bg-red-500/10 border-red-500/30 text-red-400'
            }`}>
              {wlMessage.text}
            </div>
          )}

          {/* Add form */}
          {canManage && (
            <div className="bg-slate-900/60 backdrop-blur-sm border border-slate-800/60 rounded-xl p-4">
              <h2 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
                <Shield className="w-4 h-4 text-emerald-400" /> Thêm IP vào Whitelist
              </h2>
              <div className="flex gap-2">
                <input
                  value={newWlIp}
                  onChange={(e) => setNewWlIp(e.target.value)}
                  placeholder="192.168.1.100"
                  className="w-44 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 font-mono text-sm focus:outline-none focus:border-emerald-500 transition-colors"
                />
                <input
                  value={newWlReason}
                  onChange={(e) => setNewWlReason(e.target.value)}
                  placeholder="Lý do (tuỳ chọn)"
                  className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 text-sm focus:outline-none focus:border-emerald-500 transition-colors"
                />
                <button
                  onClick={handleAddWhitelist}
                  disabled={wlLoading || !newWlIp.trim()}
                  className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                  <Plus className="w-4 h-4" /> Thêm
                </button>
              </div>
            </div>
          )}

          {/* Whitelist table */}
          <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl border border-slate-800/60 overflow-hidden">
            <table className="w-full text-left">
              <thead className="bg-slate-800/80 border-b border-slate-700/60">
                <tr>
                  <th className={thClass}>IP Address</th>
                  <th className={thClass}>Lý do</th>
                  <th className={thClass}>Ngày thêm</th>
                  {canManage && <th className={`${thClass} text-right`}>Thao tác</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {whitelist.length === 0 ? (
                  <tr><td colSpan={4} className="px-4 py-10 text-center text-slate-600">Chưa có IP nào trong whitelist</td></tr>
                ) : whitelist.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className={`${tdClass} font-mono text-emerald-400`}>{item.ip_address}</td>
                    <td className={`${tdClass} text-slate-400`}>{item.reason || '—'}</td>
                    <td className={`${tdClass} text-slate-500 text-xs`}>{formatDatetime(item.created_at)}</td>
                    {canManage && (
                      <td className={`${tdClass} text-right`}>
                        <button
                          onClick={() => handleRemoveWhitelist(item.id, item.ip_address)}
                          className="p-1.5 bg-red-500/10 text-red-400 hover:bg-red-500/20 rounded border border-red-500/20 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Block IP Modal */}
      <BlockIPModal
        isOpen={showBlockIPModal}
        onClose={() => setShowBlockIPModal(false)}
        onBlock={handleAddBlock}
      />
    </div>
  );
}
