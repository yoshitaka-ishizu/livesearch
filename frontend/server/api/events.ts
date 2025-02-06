import { readFileSync } from 'fs'
import { resolve } from 'path'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'
import type { Schedule } from '~/types'

export default defineEventHandler((event) => {
  try {
    // ファイルパスの解決
    const __filename = fileURLToPath(import.meta.url)
    const __dirname = dirname(__filename)
    const filePath = join(__dirname, '../../../backend/data/events.json')
    
    console.log('Reading file from:', filePath) // デバッグ用

    const jsonData = readFileSync(filePath, 'utf-8')
    const events: Schedule[] = JSON.parse(jsonData)

    // クエリパラメータの取得
    const query = getQuery(event)
    const artist = query.artist as string
    const date = query.date as string

    console.log('Query params:', { artist, date }) // デバッグ用

    // 日付指定がある場合
    if (date) {
      // 日付の完全一致検索
      const filteredEvents = events.filter(event => event.date === date)
      console.log(`Searching for date: ${date}`) // デバッグ用
      console.log(`Found ${filteredEvents.length} events for date ${date}`) // デバッグ用
      filteredEvents.forEach(event => {
        console.log(`Event date: ${event.date}, matches: ${event.date === date}`) // デバッグ用
      })
      return filteredEvents
    }

    // アーティスト指定がある場合
    if (artist) {
      return events.filter(event => event.artist === artist)
    }

    return events
  } catch (error) {
    console.error('Error reading events:', error)
    console.error('Error details:', error) // より詳細なエラー情報
    return []
  }
})