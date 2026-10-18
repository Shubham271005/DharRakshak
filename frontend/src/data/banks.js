/*
 * Bank comparison + past loans for the Loans screen. SAMPLE DATA.
 *
 * KCC rates follow the national Modified Interest Subvention Scheme: 7% a year
 * up to ₹3 lakh, 3% back for on-time repayment (effective 4%). Rates above
 * ₹3 lakh, fees and limits are indicative — always confirm with the bank.
 */

const D = {
  kcc_form: { en: 'KCC application form', hi: 'केसीसी आवेदन फॉर्म' },
  id: { en: 'Aadhaar / Voter ID', hi: 'आधार / वोटर आईडी' },
  address: { en: 'Address proof', hi: 'पते का प्रमाण' },
  land: { en: 'Land record (khatauni / 7-12)', hi: 'भूमि रिकॉर्ड (खतौनी / 7-12)' },
  photo: { en: '2 passport-size photos', hi: '2 पासपोर्ट साइज फोटो' },
  crop_plan: { en: 'Sowing / crop plan', hi: 'बुवाई / फसल योजना' },
  no_dues: { en: 'No-dues certificate (other banks)', hi: 'अन्य बैंकों से नो-ड्यूज़ प्रमाणपत्र' },
  pan: { en: 'PAN card (above ₹2 lakh)', hi: 'पैन कार्ड (₹2 लाख से ऊपर)' },
  society: { en: 'Society membership slip', hi: 'सहकारी समिति सदस्यता पर्ची' },
}

export const BANKS = [
  {
    id: 'sbi', name: 'State Bank of India', short: 'SBI', tone: 'from-sky-500 to-blue-700',
    rate: 7.0, effective: 4.0, above: '≈ 9.0–10.5%', maxNoCollateral: 200000, fee: { en: 'Nil up to ₹3 lakh', hi: '₹3 लाख तक शून्य' },
    days: 14, docs: [D.kcc_form, D.id, D.address, D.land, D.photo, D.no_dues],
  },
  {
    id: 'pnb', name: 'Punjab National Bank', short: 'PNB', tone: 'from-rose-500 to-red-700',
    rate: 7.0, effective: 4.0, above: '≈ 9.25–10.5%', maxNoCollateral: 200000, fee: { en: 'Nil up to ₹3 lakh', hi: '₹3 लाख तक शून्य' },
    days: 14, docs: [D.kcc_form, D.id, D.land, D.photo, D.crop_plan],
  },
  {
    id: 'bob', name: 'Bank of Baroda', short: 'BoB', tone: 'from-orange-400 to-orange-600',
    rate: 7.0, effective: 4.0, above: '≈ 9.15–10.4%', maxNoCollateral: 200000, fee: { en: 'Nil up to ₹3 lakh', hi: '₹3 लाख तक शून्य' },
    days: 15, docs: [D.kcc_form, D.id, D.address, D.land, D.photo],
  },
  {
    id: 'hdfc', name: 'HDFC Bank', short: 'HDFC', tone: 'from-indigo-500 to-blue-800',
    rate: 7.0, effective: 4.0, above: '≈ 9.5–12%', maxNoCollateral: 200000, fee: { en: 'Up to 1% above ₹3 lakh', hi: '₹3 लाख से ऊपर 1% तक' },
    days: 10, docs: [D.kcc_form, D.id, D.address, D.land, D.photo, D.pan],
  },
  {
    id: 'coop', name: 'District Cooperative Bank', short: 'DCCB', tone: 'from-emerald-500 to-green-700',
    rate: 7.0, effective: 4.0, above: '≈ 9–11%', maxNoCollateral: 160000, fee: { en: 'Small society fee', hi: 'छोटी समिति फीस' },
    days: 21, docs: [D.kcc_form, D.id, D.land, D.photo, D.society],
  },
]

export const PAST_LOANS = [
  {
    id: 'kcc-2025', name: { en: 'Kisan Credit Card — Rabi 2024-25', hi: 'किसान क्रेडिट कार्ड — रबी 2024-25' },
    bank: 'State Bank of India', amount: 50000, rate: 4.0, from: '2024-11-05', to: '2025-05-28', onTime: true,
  },
  {
    id: 'kcc-2024', name: { en: 'Kisan Credit Card — Kharif 2024', hi: 'किसान क्रेडिट कार्ड — खरीफ 2024' },
    bank: 'State Bank of India', amount: 40000, rate: 4.0, from: '2024-06-12', to: '2024-10-30', onTime: true,
  },
  {
    id: 'pump-2023', name: { en: 'Pump-set loan', hi: 'पंप-सेट ऋण' },
    bank: 'District Cooperative Bank', amount: 35000, rate: 9.5, from: '2023-02-01', to: '2024-01-31', onTime: false,
  },
]
