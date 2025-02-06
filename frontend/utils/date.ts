// utils/date.ts として新規作成
import { format, parseISO } from 'date-fns'

export const formatDateForApi = (date: string | Date): string => {
  if (typeof date === 'string') {
    return format(parseISO(date), 'yyyy/MM/dd')
  }
  return format(date, 'yyyy/MM/dd')
}