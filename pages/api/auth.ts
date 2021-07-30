import NextAuth from 'next-auth'
import Providers from 'next-auth/providers'

export default NextAuth({
  // Configure one or more authentication providers
  providers: [
    Providers.Twitter({
      clientId: process.env.TWITTER_ID,
      clientSecret: process.env.TWITTER_SECRET
    })
  ],

  // A database is optional, but required to persist accounts in a database
  database: process.env.DATABASE_URL,
  secret: process.env.SECRET,
  debug: true
})
