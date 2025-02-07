import type { Schedule } from '~/types'

export default defineEventHandler(async (event) => {
 try {
   // GitHubのRawコンテンツURLからデータを取得
   const response = await fetch('https://raw.githubusercontent.com/yoshitaka-ishizu/livesearch/main/backend/data/events.json')
   if (!response.ok) {
     throw new Error(`HTTP error! status: ${response.status}`)
   }
   const events: Schedule[] = await response.json()

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
   console.error('Error fetching events:', error)
   console.error('Error details:', error) // より詳細なエラー情報
   return []
 }
})