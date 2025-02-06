import type { Schedule } from '~/types'

interface ArtistOption {
  name: string;
  hasSchedule: boolean;
}

export const useEvents = () => {
  const runtimeConfig = useRuntimeConfig()

  const getArtistList = async (): Promise<ArtistOption[]> => {
    try {
      const response = await fetch('/api/events')
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const events: Schedule[] = await response.json()
      
      // アーティストごとにスケジュールの有無をチェック
      const artistMap = new Map<string, boolean>()
      const currentDate = new Date()
      currentDate.setHours(0, 0, 0, 0)

      events.forEach(event => {
        const eventDate = new Date(event.date)
        // 現在日以降のスケジュールがあるかどうかをチェック
        if (eventDate >= currentDate) {
          artistMap.set(event.artist, true)
        } else if (!artistMap.has(event.artist)) {
          artistMap.set(event.artist, false)
        }
      })

      // MapをArray<ArtistOption>に変換してソート
      return Array.from(artistMap.entries())
        .map(([name, hasSchedule]) => ({
          name,
          hasSchedule
        }))
        .sort((a, b) => a.name.localeCompare(b.name))
    } catch (error) {
      console.error('Failed to fetch artists:', error)
      return []
    }
  }

  const getArtists = async () => {
    try {
      const response = await fetch('/api/events')
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data: Schedule[] = await response.json()
      
      // アーティスト名の重複を除去してソート
      const uniqueArtists = [...new Set(data.map(event => event.artist))]
      return uniqueArtists.sort()
    } catch (error) {
      console.error('Failed to fetch artists:', error)
      return []
    }
  }

  const getScheduleByArtist = async (artist: string) => {
    try {
      const response = await fetch(`/api/events?artist=${encodeURIComponent(artist)}`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data: Schedule[] = await response.json()
      
      // 現在日以降のスケジュールのみをフィルタリング
      const currentDate = new Date()
      currentDate.setHours(0, 0, 0, 0)
      
      return data.filter(event => {
        const eventDate = new Date(event.date)
        return eventDate >= currentDate
      })
    } catch (error) {
      console.error('Failed to fetch schedule:', error)
      return []
    }
  }

  const getEventsByDate = async (date: string) => {
    try {
      console.log('Fetching events for date:', date) // デバッグ用
      const response = await fetch(`/api/events?date=${encodeURIComponent(date)}`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data: Schedule[] = await response.json()
      console.log('Received events:', data) // デバッグ用
      return data
    } catch (error) {
      console.error('Failed to fetch events:', error)
      return []
    }
  }

  const getEventCountByDate = async (date: string) => {
    try {
      const events = await getEventsByDate(date)
      return events.length
    } catch (error) {
      console.error('Failed to fetch event count:', error)
      return 0
    }
  }

  return {
    getArtists,
    getArtistList,
    getScheduleByArtist,
    getEventsByDate,
    getEventCountByDate
  }
}