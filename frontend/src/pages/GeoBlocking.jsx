import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { Globe, Ban, CheckCircle2, AlertCircle, Search, Eye, ChevronDown, Shield, Lock, Unlock } from 'lucide-react';
import { hasRole } from '../lib/auth';
import {
  lookupGeoIP, fetchGeoAllow, fetchGeoWatch, addGeoAllow, removeGeoAllow,
  addGeoWatch, removeGeoWatch, fetchGeoBlocks, addGeoBlock, removeGeoBlock,
} from '../lib/api';

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

export default function GeoBlocking() {
  const [geoRules, setGeoRules] = useState([]);
  const [allowRules, setAllowRules] = useState([]);
  const [watchRules, setWatchRules] = useState([]);
  const [lookupIp, setLookupIp] = useState('');
  const [lookupResult, setLookupResult] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [message, setMessage] = useState({ type: '', text: '' });
  const [loading, setLoading] = useState(false);

  const flashMessage = useCallback((type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage({ type: '', text: '' }), 3000);
  }, []);

  const loadGeoBlocks = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchGeoBlocks();
      setGeoRules(Array.isArray(data) ? data : []);
    } catch (err) {
      flashMessage('error', 'Không thể tải quy tắc Geo Blocking: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  }, [flashMessage]);

  const getCountryStatus = useCallback((countryCode) => {
    const isBlocked = geoRules.some(r => r.country_code === countryCode && r.is_active);
    const isAllowed = allowRules.some(r => r.country_code === countryCode);
    const isWatched = watchRules.some(r => r.country_code === countryCode);
    return { isBlocked, isAllowed, isWatched };
  }, [geoRules, allowRules, watchRules]);

  const handleCountryAction = useCallback(async (countryCode, countryName, action) => {
    if (!hasRole(['admin'])) {
      flashMessage('error', 'Bạn không có quyền thực hiện thao tác này.');
      return;
    }

    // Fallback to country code if country_name is not provided
    const finalCountryName = countryName || countryCode;

    try {
      if (action === 'block') {
        await addGeoBlock({ country_code: countryCode, country_name: finalCountryName });
        flashMessage('success', `Đã chặn truy cập từ ${finalCountryName}.`);
        // Optimistically update state without loading
        setGeoRules(prev => [...prev, { country_code: countryCode, country_name: finalCountryName, is_active: true }]);
      } else if (action === 'allow') {
        await addGeoAllow({ country_code: countryCode, country_name: finalCountryName });
        flashMessage('success', `Đã cho phép truy cập từ ${finalCountryName}.`);
        fetchGeoAllow().then(setAllowRules);
      } else if (action === 'watch') {
        await addGeoWatch({ country_code: countryCode, country_name: finalCountryName });
        flashMessage('success', `Đã thêm ${finalCountryName} vào danh sách theo dõi.`);
        fetchGeoWatch().then(setWatchRules);
      } else if (action === 'unblock') {
        await removeGeoBlock(countryCode);
        flashMessage('success', `Đã gỡ chặn ${finalCountryName}.`);
        // Optimistically update state without loading
        setGeoRules(prev => prev.filter(r => r.country_code !== countryCode));
      } else if (action === 'unallow') {
        await removeGeoAllow(countryCode);
        flashMessage('success', `Đã gỡ cho phép ${finalCountryName}.`);
        fetchGeoAllow().then(setAllowRules);
      } else if (action === 'unwatch') {
        await removeGeoWatch(countryCode);
        flashMessage('success', `Đã gỡ theo dõi ${finalCountryName}.`);
        fetchGeoWatch().then(setWatchRules);
      }
    } catch (err) {
      flashMessage('error', 'Lỗi khi thực hiện thao tác: ' + (err.response?.data?.detail || err.message));
      // Reload data on error to sync state
      loadGeoBlocks();
    }
  }, [flashMessage, loadGeoBlocks]);

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

  useEffect(() => {
    if (!hasRole(['admin'])) {
      flashMessage('error', 'Bạn không có quyền truy cập trang này.');
      return;
    }
    loadGeoBlocks();
    fetchGeoAllow().then(setAllowRules).catch(() => {});
    fetchGeoWatch().then(setWatchRules).catch(() => {});
  }, [flashMessage, loadGeoBlocks]);

  const handleLookup = async () => {
    if (!lookupIp.trim()) return;
    try {
      const result = await lookupGeoIP(lookupIp.trim());
      setLookupResult(result);
    } catch (err) {
      flashMessage('error', 'Không tra cứu được IP');
    }
  };

  if (!hasRole(['admin'])) {
    return (
      <div className="p-6 text-center text-red-500">
        <AlertCircle className="w-12 h-12 mx-auto mb-3" />
        <p className="text-xl font-semibold">Truy cập bị từ chối</p>
        <p className="text-gray-500">Bạn không có quyền xem trang này.</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Globe className="w-8 h-8 text-purple-500" />
        <h1 className="text-2xl font-bold text-purple-500">Quản lý Geo Blocking</h1>
      </div>

      {/* Toast Notification */}
      {message.text && (
        <div className={`fixed top-4 right-4 p-4 rounded-lg shadow-lg flex items-center gap-3 z-50 animate-in slide-in-from-right-5 duration-300 ${
          message.type === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'
        }`}>
          {message.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          <span className="text-sm font-medium">{message.text}</span>
        </div>
      )}

      {/* IP Lookup Section */}
      <div className="bg-white p-4 rounded-xl border border-gray-200 mb-6">
        <h2 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <Search className="w-4 h-4 text-blue-500" /> Tra cứu quốc gia từ IP
        </h2>
        <div className="flex gap-2">
          <input
            value={lookupIp}
            onChange={(e) => setLookupIp(e.target.value)}
            placeholder="185.221.20.10"
            className="flex-1 bg-white border border-gray-300 rounded-lg px-3 py-2 text-gray-700 font-mono text-sm"
          />
          <button type="button" onClick={handleLookup} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white text-sm">Tra cứu</button>
        </div>
        {lookupResult && (
          <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-600 mb-2">
              <span className="font-mono text-blue-600">{lookupResult.ip}</span>
              {' → '}
              <strong className="text-gray-800">{lookupResult.country_name || 'Unknown'}</strong>
              {lookupResult.country_code && ` (${lookupResult.country_code})`}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => handleCountryAction(lookupResult.country_code, lookupResult.country_name, 'block')}
                className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs rounded-lg flex items-center gap-1"
              >
                <Ban className="w-3 h-3" /> Chặn
              </button>
              <button
                onClick={() => handleCountryAction(lookupResult.country_code, lookupResult.country_name, 'allow')}
                className="px-3 py-1.5 bg-green-600 hover:bg-green-500 text-white text-xs rounded-lg flex items-center gap-1"
              >
                <CheckCircle2 className="w-3 h-3" /> Cho phép
              </button>
              <button
                onClick={() => handleCountryAction(lookupResult.country_code, lookupResult.country_name, 'watch')}
                className="px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 text-white text-xs rounded-lg flex items-center gap-1"
              >
                <Eye className="w-3 h-3" /> Theo dõi
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Common Countries Quick Block Section */}
      <div className="bg-white p-4 rounded-xl border border-gray-200 mb-6">
        <h2 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <Ban className="w-4 h-4 text-purple-500" /> Chặn nhanh các quốc gia phổ biến
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
          {COMMON_COUNTRIES.map((c) => {
            const status = getCountryStatus(c.code);
            return (
              <button
                key={c.code}
                onClick={() => handleCountryAction(c.code, c.name, status.isBlocked ? 'unblock' : 'block')}
                disabled={loading || !hasRole(['admin'])}
                className={`px-3 py-2 text-xs rounded-lg border font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-1 ${
                  status.isBlocked ? 'bg-purple-600 text-white border-purple-600' : 'bg-gray-100 text-gray-600 border-gray-300 hover:border-purple-400'
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
      <div className="bg-white p-4 rounded-xl border border-gray-200 mb-6">
        <h2 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <Globe className="w-4 h-4 text-purple-500" /> Tìm kiếm quốc gia
        </h2>
        <div className="flex gap-2">
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Nhập tên quốc gia hoặc mã quốc gia..."
            className="flex-1 bg-white border border-gray-300 rounded-lg px-3 py-2 text-gray-700 text-sm"
          />
        </div>
        {searchQuery && filteredCountries.length > 0 && (
          <div className="mt-3 max-h-48 overflow-auto border border-gray-200 rounded-lg">
            {filteredCountries.slice(0, 20).map((c) => {
              const status = getCountryStatus(c.value);
              const countryName = c.label;
              return (
                <div key={c.value} className="flex items-center justify-between p-2 hover:bg-gray-50 border-b border-gray-100 last:border-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-800">{c.label}</span>
                    <span className="text-xs text-gray-500">({c.value})</span>
                    {status.isBlocked && <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full">Đã chặn</span>}
                    {status.isAllowed && <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">Đã cho phép</span>}
                    {status.isWatched && <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded-full">Đang theo dõi</span>}
                  </div>
                  <div className="flex gap-1">
                    <button
                      onClick={() => handleCountryAction(c.value, countryName, status.isBlocked ? 'unblock' : 'block')}
                      className={`px-2 py-1 text-xs rounded ${status.isBlocked ? 'bg-gray-200 text-gray-600' : 'bg-red-600 text-white hover:bg-red-500'}`}
                    >
                      {status.isBlocked ? 'Gỡ chặn' : 'Chặn'}
                    </button>
                    <button
                      onClick={() => handleCountryAction(c.value, countryName, status.isAllowed ? 'unallow' : 'allow')}
                      className={`px-2 py-1 text-xs rounded ${status.isAllowed ? 'bg-gray-200 text-gray-600' : 'bg-green-600 text-white hover:bg-green-500'}`}
                    >
                      {status.isAllowed ? 'Gỡ cho phép' : 'Cho phép'}
                    </button>
                    <button
                      onClick={() => handleCountryAction(c.value, countryName, status.isWatched ? 'unwatch' : 'watch')}
                      disabled={status.isBlocked || status.isAllowed}
                      className={`px-2 py-1 text-xs rounded ${status.isWatched ? 'bg-gray-200 text-gray-600' : 'bg-yellow-600 text-white hover:bg-yellow-500'} ${status.isBlocked || status.isAllowed ? 'opacity-50 cursor-not-allowed' : ''}`}
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
          <p className="mt-3 text-sm text-gray-500">Không tìm thấy quốc gia nào.</p>
        )}
      </div>

      {/* Active Rules Section */}
      <div className="bg-white p-4 rounded-xl border border-gray-200">
        <h2 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <Shield className="w-4 h-4 text-purple-500" /> Các quốc gia đang có quy tắc ({allCountriesWithStatus.length})
        </h2>
        {loading ? (
          <p className="text-gray-500">Đang tải...</p>
        ) : allCountriesWithStatus.length > 0 ? (
          <div className="overflow-auto max-h-96">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-600 text-xs uppercase sticky top-0">
                <tr>
                  <th className="px-4 py-3 text-left">Quốc gia</th>
                  <th className="px-4 py-3 text-left">Mã</th>
                  <th className="px-4 py-3 text-left">Trạng thái</th>
                  <th className="px-4 py-3 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {allCountriesWithStatus.map((c) => {
                  const countryName = c.label;
                  return (
                    <tr key={c.value} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-800">{c.label}</td>
                      <td className="px-4 py-3 text-gray-600 font-mono">{c.value}</td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1 flex-wrap">
                          {c.status.isBlocked && (
                            <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full flex items-center gap-1">
                              <Lock className="w-3 h-3" /> Đã chặn
                            </span>
                          )}
                          {c.status.isAllowed && (
                            <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full flex items-center gap-1">
                              <Unlock className="w-3 h-3" /> Đã cho phép
                            </span>
                          )}
                          {c.status.isWatched && (
                            <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded-full flex items-center gap-1">
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
                              className="px-2 py-1 bg-gray-200 text-gray-600 text-xs rounded hover:bg-gray-300"
                            >
                              Gỡ chặn
                            </button>
                          )}
                          {c.status.isAllowed && (
                            <button
                              onClick={() => handleCountryAction(c.value, countryName, 'unallow')}
                              className="px-2 py-1 bg-gray-200 text-gray-600 text-xs rounded hover:bg-gray-300"
                            >
                              Gỡ cho phép
                            </button>
                          )}
                          {c.status.isWatched && (
                            <button
                              onClick={() => handleCountryAction(c.value, countryName, 'unwatch')}
                              className="px-2 py-1 bg-gray-200 text-gray-600 text-xs rounded hover:bg-gray-300"
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
          <p className="text-gray-500">Chưa có quốc gia nào có quy tắc.</p>
        )}
      </div>
    </div>
  );
}

