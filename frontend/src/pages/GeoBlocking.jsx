import React, { useEffect, useState } from 'react';
import { Globe, Ban, CheckCircle2, AlertCircle, Search, Eye } from 'lucide-react';
import { hasRole } from '../lib/auth';
import {
  lookupGeoIP, fetchGeoAllow, fetchGeoWatch, addGeoAllow, removeGeoAllow,
  addGeoWatch, removeGeoWatch, fetchGeoBlocks, addGeoBlock, removeGeoBlock,
} from '../lib/api';
import Select from 'react-select'; // Cần cài đặt: npm install react-select

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

// Danh sách tất cả các quốc gia (có thể lấy từ một API hoặc file JSON)
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
  { value: 'KG', label: 'Kyrgyzstan' }, { value: 'LA', label: 'Lao People\'s Democratic Republic' },
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
].map(c => ({ value: c.value, label: `${c.label} (${c.value})` }));

export default function GeoBlocking() {
  const [geoRules, setGeoRules] = useState([]);
  const [allowRules, setAllowRules] = useState([]);
  const [watchRules, setWatchRules] = useState([]);
  const [policyTab, setPolicyTab] = useState('block');
  const [lookupIp, setLookupIp] = useState('');
  const [lookupResult, setLookupResult] = useState(null);
  const [selectedCountry, setSelectedCountry] = useState(null);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [loading, setLoading] = useState(false);

  const flashMessage = (type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage({ type: '', text: '' }), 3000);
  };

  useEffect(() => {
    if (!hasRole(['admin'])) {
      flashMessage('error', 'Bạn không có quyền truy cập trang này.');
      return;
    }
    loadGeoBlocks();
    fetchGeoAllow().then(setAllowRules).catch(() => {});
    fetchGeoWatch().then(setWatchRules).catch(() => {});
  }, []);

  const handleLookup = async () => {
    if (!lookupIp.trim()) return;
    try {
      const result = await lookupGeoIP(lookupIp.trim());
      setLookupResult(result);
    } catch (err) {
      flashMessage('error', 'Không tra cứu được IP');
    }
  };

  const loadGeoBlocks = async () => {
    setLoading(true);
    try {
      const data = await fetchGeoBlocks();
      setGeoRules(Array.isArray(data) ? data : []);
    } catch (err) {
      flashMessage('error', 'Không thể tải quy tắc Geo Blocking: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleAddGeoBlock = async (countryCode, countryName) => {
    if (!hasRole(['admin'])) {
      flashMessage('error', 'Bạn không có quyền thực hiện thao tác này.');
      return;
    }
    const cc = countryCode || (selectedCountry ? selectedCountry.value : '');
    const cn = countryName || (selectedCountry ? selectedCountry.label.split('(')[0].trim() : '');

    if (!cc) {
      flashMessage('error', 'Vui lòng chọn một quốc gia.');
      return;
    }

    try {
      await addGeoBlock({ country_code: cc, country_name: cn });
      flashMessage('success', `Đã chặn truy cập từ ${cn || cc}.`);
      setSelectedCountry(null);
      loadGeoBlocks();
    } catch (err) {
      flashMessage('error', 'Lỗi khi thêm quy tắc: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleRemoveGeoBlock = async (countryCode) => {
    if (!hasRole(['admin'])) {
      flashMessage('error', 'Bạn không có quyền thực hiện thao tác này.');
      return;
    }
    if (!window.confirm(`Bạn có chắc muốn gỡ chặn truy cập từ ${countryCode}?`)) {
      return;
    }
    try {
      await removeGeoBlock(countryCode);
      flashMessage('success', `Đã gỡ chặn truy cập từ ${countryCode}.`);
      loadGeoBlocks();
    } catch (err) {
      flashMessage('error', 'Lỗi khi gỡ quy tắc: ' + (err.response?.data?.detail || err.message));
    }
  };

  if (!hasRole(['admin'])) {
    return (
      <div className="p-6 text-center text-red-500">
        <AlertCircle className="w-12 h-12 mx-auto mb-3" />
        <p className="text-xl font-semibold">Truy cập bị từ chối</p>
        <p className="text-gray-400">Bạn không có quyền xem trang này.</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Globe className="w-8 h-8 text-purple-500" />
        <h1 className="text-2xl font-bold text-white">Quản lý Geo Blocking</h1>
      </div>

      {message.text && (
        <div className={`mb-4 p-3 rounded-lg flex items-center gap-2 ${
          message.type === 'success' ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'
        }`}>
          {message.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          {message.text}
        </div>
      )}

      <div className="bg-gray-800 p-4 rounded-xl border border-gray-700 mb-6">
        <h2 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <Search className="w-4 h-4 text-blue-400" /> Tra cứu quốc gia từ IP
        </h2>
        <div className="flex gap-2">
          <input
            value={lookupIp}
            onChange={(e) => setLookupIp(e.target.value)}
            placeholder="185.221.20.10"
            className="flex-1 bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white font-mono text-sm"
          />
          <button type="button" onClick={handleLookup} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white text-sm">Tra cứu</button>
        </div>
        {lookupResult && (
          <p className="mt-2 text-sm text-gray-300">
            <span className="font-mono text-blue-400">{lookupResult.ip}</span>
            {' → '}
            <strong>{lookupResult.country_name || 'Unknown'}</strong>
            {lookupResult.country_code && ` (${lookupResult.country_code})`}
          </p>
        )}
      </div>

      <div className="flex gap-2 mb-4 border-b border-gray-700">
        {[
          { id: 'block', label: 'Chặn', icon: Ban },
          { id: 'allow', label: 'Cho phép', icon: CheckCircle2 },
          { id: 'watch', label: 'Theo dõi', icon: Eye },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setPolicyTab(id)}
            className={`flex items-center gap-1 px-4 py-2 text-sm border-b-2 -mb-px ${
              policyTab === id ? 'border-purple-500 text-purple-300' : 'border-transparent text-gray-500'
            }`}
          >
            <Icon className="w-4 h-4" /> {label}
          </button>
        ))}
      </div>

      {policyTab === 'block' && (
      <>
      {/* Quick Add Section */}
      <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg mb-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Ban className="w-5 h-5 text-purple-400" /> Chặn nhanh các quốc gia phổ biến
        </h2>
        <div className="flex flex-wrap gap-2 mb-4">
          {COMMON_COUNTRIES.map((c) => {
            const active = geoRules.some((r) => r.country_code === c.code && r.is_active);
            return (
              <button
                key={c.code}
                onClick={() => active ? handleRemoveGeoBlock(c.code) : handleAddGeoBlock(c.code, c.name)}
                disabled={loading || !hasRole(['admin'])}
                className={`px-3 py-1.5 text-xs rounded-lg border font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                  active ? 'bg-purple-600 text-white border-purple-600' : 'bg-gray-700 text-gray-300 border-gray-600 hover:border-purple-400'
                }`}
              >
                {active ? '✓ ' : ''}{c.code} — {c.name}
              </button>
            );
          })}
        </div>

        {/* Manual Add with Select */}
        <h2 className="text-lg font-semibold text-white mb-4 mt-6 flex items-center gap-2">
          <Globe className="w-5 h-5 text-purple-400" /> Chặn quốc gia bất kỳ
        </h2>
        <div className="flex gap-3">
          <div className="flex-1">
            <Select
              options={ALL_COUNTRIES}
              value={selectedCountry}
              onChange={setSelectedCountry}
              isDisabled={loading || !hasRole(['admin'])}
              placeholder="Chọn một quốc gia..."
              classNamePrefix="react-select" // Để dễ dàng tùy chỉnh CSS
              styles={{
                control: (baseStyles, state) => ({
                  ...baseStyles,
                  backgroundColor: '#1f2937', // bg-gray-800
                  borderColor: '#4b5563', // border-gray-600
                  color: '#e5e7eb', // text-gray-200
                  '&:hover': { borderColor: '#8b5cf6' }, // hover:border-purple-500
                }),
                singleValue: (baseStyles) => ({ ...baseStyles, color: '#e5e7eb' }),
                input: (baseStyles) => ({ ...baseStyles, color: '#e5e7eb' }),
                placeholder: (baseStyles) => ({ ...baseStyles, color: '#9ca3af' }),
                menu: (baseStyles) => ({ ...baseStyles, backgroundColor: '#1f2937' }),
                option: (baseStyles, state) => ({
                  ...baseStyles,
                  backgroundColor: state.isFocused ? '#4c1d95' : '#1f2937', // focus:bg-purple-900
                  color: '#e5e7eb',
                  '&:active': { backgroundColor: '#6d28d9' }, // active:bg-purple-700
                }),
              }}
            />
          </div>
          <button
            onClick={() => handleAddGeoBlock()}
            disabled={!selectedCountry || loading || !hasRole(['admin'])}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-500 rounded-lg text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Chặn Quốc gia
          </button>
        </div>
      </div>

      {/* Active Geo-block Rules Section */}
      <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg">
        <h2 className="text-lg font-semibold text-white mb-4">
          Các quy tắc Geo Blocking đang hoạt động ({geoRules.filter(r => r.is_active).length})
        </h2>
        {loading ? (
          <p className="text-gray-400">Đang tải quy tắc...</p>
        ) : geoRules.filter(r => r.is_active).length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {geoRules.filter(r => r.is_active).map((rule) => (
              <div key={rule.id} className="flex items-center gap-2 px-3 py-1.5 bg-purple-900/30 border border-purple-700 rounded-lg">
                <span className="text-sm font-semibold text-purple-300">{rule.country_code}</span>
                {rule.country_name && <span className="text-xs text-gray-400">{rule.country_name}</span>}
                {hasRole(['admin']) && (
                  <button
                    onClick={() => handleRemoveGeoBlock(rule.country_code)}
                    className="text-purple-400 hover:text-red-400 ml-1"
                    title="Gỡ chặn"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-400">Chưa có quy tắc Geo Blocking nào đang hoạt động.</p>
        )}
      </div>
      </>
      )}

      {policyTab === 'allow' && (
        <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 space-y-4">
          <h2 className="text-lg font-semibold text-green-400">Quốc gia được phép</h2>
          <div className="flex flex-wrap gap-2">
            {allowRules.map((r) => (
              <span key={r.country_code} className="px-3 py-1 bg-green-900/30 border border-green-700 rounded-lg text-sm text-green-300">
                {r.country_code} {r.country_name}
                <button type="button" className="ml-2 text-red-400" onClick={() => removeGeoAllow(r.country_code).then(() => fetchGeoAllow().then(setAllowRules))}>✕</button>
              </span>
            ))}
          </div>
          <button
            type="button"
            disabled={!selectedCountry}
            onClick={() => selectedCountry && addGeoAllow({ country_code: selectedCountry.value, country_name: selectedCountry.label.split('(')[0].trim() }).then(() => { fetchGeoAllow().then(setAllowRules); flashMessage('success', 'Đã thêm allow'); })}
            className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-white text-sm disabled:opacity-50"
          >
            Thêm quốc gia đã chọn (dùng dropdown bên tab Chặn)
          </button>
        </div>
      )}

      {policyTab === 'watch' && (
        <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 space-y-4">
          <h2 className="text-lg font-semibold text-yellow-400">Quốc gia theo dõi</h2>
          <div className="flex flex-wrap gap-2">
            {watchRules.map((r) => (
              <span key={r.country_code} className="px-3 py-1 bg-yellow-900/30 border border-yellow-700 rounded-lg text-sm text-yellow-300">
                {r.country_code} {r.country_name}
                <button type="button" className="ml-2 text-red-400" onClick={() => removeGeoWatch(r.country_code).then(() => fetchGeoWatch().then(setWatchRules))}>✕</button>
              </span>
            ))}
          </div>
          <button
            type="button"
            disabled={!selectedCountry}
            onClick={() => selectedCountry && addGeoWatch({ country_code: selectedCountry.value, country_name: selectedCountry.label.split('(')[0].trim() }).then(() => { fetchGeoWatch().then(setWatchRules); flashMessage('success', 'Đã thêm watch'); })}
            className="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 rounded-lg text-white text-sm disabled:opacity-50"
          >
            Thêm quốc gia theo dõi (dùng dropdown bên tab Chặn)
          </button>
        </div>
      )}
    </div>
  );
}