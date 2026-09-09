export type PropertyDefinition = {
  id: string;
  zh: string;
  en: string;
  aliases: string[];
  dimension: string;
  preferredUnit?: string;
  units?: string[];
};

/** Lightweight vocabulary: suggestions only, never an input validation gate. */
export const propertyDictionary: PropertyDefinition[] = [
  {
    id: 'temperature',
    zh: '温度',
    en: 'Temperature',
    aliases: ['温', 'temp', 'T'],
    dimension: 'Temperature',
    preferredUnit: '℃',
    units: ['℃', 'K', '°F']
  },
  {
    id: 'amount',
    zh: '添加量',
    en: 'Amount',
    aliases: ['用量', '加入量', 'dose'],
    dimension: 'Mass',
    preferredUnit: 'g',
    units: ['mg', 'g', 'kg', 't']
  },
  {
    id: 'mass',
    zh: '质量',
    en: 'Mass',
    aliases: ['重量', 'mass'],
    dimension: 'Mass',
    preferredUnit: 'g',
    units: ['mg', 'g', 'kg', 't']
  },
  {
    id: 'volume',
    zh: '体积',
    en: 'Volume',
    aliases: ['容量', 'volume'],
    dimension: 'Volume',
    preferredUnit: 'mL',
    units: ['μL', 'mL', 'L']
  },
  {
    id: 'time',
    zh: '时间',
    en: 'Time',
    aliases: ['时长', 'duration'],
    dimension: 'Time',
    preferredUnit: 'min',
    units: ['s', 'min', 'h']
  },
  {
    id: 'concentration',
    zh: '浓度',
    en: 'Concentration',
    aliases: ['含量', 'concentration'],
    dimension: 'Concentration',
    preferredUnit: '%',
    units: ['%', 'wt%', 'vol%', 'mol/L', 'g/L']
  },
  {
    id: 'speed',
    zh: '转速',
    en: 'Rotation speed',
    aliases: ['rpm', '搅拌速度'],
    dimension: 'RotationalSpeed',
    preferredUnit: 'rpm',
    units: ['rpm']
  },
  {
    id: 'pressure',
    zh: '压力',
    en: 'Pressure',
    aliases: ['压强', 'pressure'],
    dimension: 'Pressure',
    preferredUnit: 'kPa',
    units: ['Pa', 'kPa', 'MPa', 'bar']
  },
  {
    id: 'flow',
    zh: '流量',
    en: 'Flow rate',
    aliases: ['流速', 'flow'],
    dimension: 'FlowRate',
    preferredUnit: 'mL/min',
    units: ['mL/min', 'L/min']
  },
  { id: 'ph', zh: 'pH', en: 'pH', aliases: ['酸碱度'], dimension: 'Dimensionless' }
];

export function filterPropertyDefinitions(query: string) {
  const needle = query.trim().toLocaleLowerCase();
  if (!needle) return propertyDictionary;
  return propertyDictionary.filter((item) =>
    [item.zh, item.en, ...item.aliases].some((value) => value.toLocaleLowerCase().includes(needle))
  );
}
