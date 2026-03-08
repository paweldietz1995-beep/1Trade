/**
 * Jupiter Aggregator Service
 * Handles token swaps on Solana via Jupiter API
 */

import { Connection, PublicKey, VersionedTransaction } from '@solana/web3.js';

// Jupiter API endpoints
const JUPITER_QUOTE_API = 'https://quote-api.jup.ag/v6/quote';
const JUPITER_SWAP_API = 'https://quote-api.jup.ag/v6/swap';

// Common token addresses
export const SOL_MINT = 'So11111111111111111111111111111111111111112';
export const USDC_MINT = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v';

// RPC Endpoints for failover
const RPC_ENDPOINTS = [
  'https://rpc.ankr.com/solana',
  'https://api.mainnet-beta.solana.com'
];

/**
 * Get connection with failover support
 */
const getConnection = async () => {
  for (const endpoint of RPC_ENDPOINTS) {
    try {
      const connection = new Connection(endpoint, {
        commitment: 'confirmed',
        confirmTransactionInitialTimeout: 60000
      });
      // Test connection
      await connection.getSlot();
      console.log(`✅ Connected to RPC: ${endpoint.substring(0, 30)}...`);
      return connection;
    } catch (error) {
      console.warn(`⚠️ RPC ${endpoint.substring(0, 30)} failed:`, error.message);
    }
  }
  throw new Error('All RPC endpoints failed');
};

/**
 * Get swap quote from Jupiter
 * @param {string} inputMint - Input token mint address
 * @param {string} outputMint - Output token mint address
 * @param {number} amount - Amount in lamports/smallest unit
 * @param {number} slippageBps - Slippage in basis points (100 = 1%)
 */
export const getQuote = async (inputMint, outputMint, amount, slippageBps = 100) => {
  try {
    console.log(`📊 Getting Jupiter quote: ${amount} ${inputMint.substring(0, 8)} -> ${outputMint.substring(0, 8)}`);
    
    const params = new URLSearchParams({
      inputMint,
      outputMint,
      amount: amount.toString(),
      slippageBps: slippageBps.toString(),
      onlyDirectRoutes: 'false',
      asLegacyTransaction: 'false'
    });

    const response = await fetch(`${JUPITER_QUOTE_API}?${params}`);
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Jupiter quote failed: ${response.status} - ${errorText}`);
    }
    
    const quote = await response.json();
    
    console.log(`✅ Quote received:`, {
      inAmount: quote.inAmount,
      outAmount: quote.outAmount,
      priceImpact: quote.priceImpactPct,
      routes: quote.routePlan?.length || 0
    });
    
    return {
      success: true,
      quote,
      inAmount: parseInt(quote.inAmount),
      outAmount: parseInt(quote.outAmount),
      priceImpact: parseFloat(quote.priceImpactPct || 0),
      otherAmountThreshold: parseInt(quote.otherAmountThreshold || 0)
    };
    
  } catch (error) {
    console.error('❌ Jupiter quote error:', error);
    return {
      success: false,
      error: error.message
    };
  }
};

/**
 * Build swap transaction from quote
 * @param {Object} quoteResponse - Quote response from getQuote
 * @param {string} userPublicKey - User's wallet public key
 */
export const buildSwapTransaction = async (quoteResponse, userPublicKey) => {
  try {
    console.log(`🔨 Building swap transaction for ${userPublicKey}`);
    
    const response = await fetch(JUPITER_SWAP_API, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        quoteResponse,
        userPublicKey,
        wrapAndUnwrapSol: true,
        dynamicComputeUnitLimit: true,
        prioritizationFeeLamports: 'auto'
      })
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Jupiter swap build failed: ${response.status} - ${errorText}`);
    }
    
    const data = await response.json();
    
    console.log('✅ Swap transaction built successfully');
    
    return {
      success: true,
      swapTransaction: data.swapTransaction
    };
    
  } catch (error) {
    console.error('❌ Swap transaction build error:', error);
    return {
      success: false,
      error: error.message
    };
  }
};

/**
 * Execute a token swap
 * @param {Object} wallet - Wallet adapter with signTransaction method
 * @param {string} inputMint - Input token mint address
 * @param {string} outputMint - Output token mint address
 * @param {number} amountLamports - Amount in lamports
 * @param {number} slippageBps - Slippage in basis points
 * @param {Function} onStatusUpdate - Callback for status updates
 */
export const executeSwap = async (
  wallet,
  inputMint,
  outputMint,
  amountLamports,
  slippageBps = 100,
  onStatusUpdate = () => {}
) => {
  try {
    // Step 1: Get quote
    onStatusUpdate('getting_quote', 'Getting swap quote...');
    const quoteResult = await getQuote(inputMint, outputMint, amountLamports, slippageBps);
    
    if (!quoteResult.success) {
      throw new Error(quoteResult.error || 'Failed to get quote');
    }
    
    // Step 2: Build transaction
    onStatusUpdate('building_transaction', 'Building transaction...');
    const buildResult = await buildSwapTransaction(
      quoteResult.quote,
      wallet.publicKey.toBase58()
    );
    
    if (!buildResult.success) {
      throw new Error(buildResult.error || 'Failed to build transaction');
    }
    
    // Step 3: Deserialize and sign transaction
    onStatusUpdate('signing', 'Please sign the transaction in your wallet...');
    
    const swapTransactionBuf = Buffer.from(buildResult.swapTransaction, 'base64');
    const transaction = VersionedTransaction.deserialize(swapTransactionBuf);
    
    // Sign with wallet
    const signedTransaction = await wallet.signTransaction(transaction);
    
    // Step 4: Send transaction
    onStatusUpdate('sending', 'Sending transaction to Solana...');
    
    const connection = await getConnection();
    const rawTransaction = signedTransaction.serialize();
    
    const txSignature = await connection.sendRawTransaction(rawTransaction, {
      skipPreflight: true,
      maxRetries: 3
    });
    
    console.log(`📤 Transaction sent: ${txSignature}`);
    
    // Step 5: Confirm transaction
    onStatusUpdate('confirming', 'Confirming transaction...');
    
    const latestBlockhash = await connection.getLatestBlockhash();
    
    const confirmation = await connection.confirmTransaction({
      signature: txSignature,
      blockhash: latestBlockhash.blockhash,
      lastValidBlockHeight: latestBlockhash.lastValidBlockHeight
    }, 'confirmed');
    
    if (confirmation.value.err) {
      throw new Error(`Transaction failed: ${JSON.stringify(confirmation.value.err)}`);
    }
    
    console.log(`✅ Transaction confirmed: ${txSignature}`);
    
    return {
      success: true,
      signature: txSignature,
      inAmount: quoteResult.inAmount,
      outAmount: quoteResult.outAmount,
      priceImpact: quoteResult.priceImpact,
      explorerUrl: `https://solscan.io/tx/${txSignature}`
    };
    
  } catch (error) {
    console.error('❌ Swap execution error:', error);
    
    // Handle user rejection
    if (error.message?.includes('User rejected')) {
      return {
        success: false,
        error: 'Transaction cancelled by user',
        cancelled: true
      };
    }
    
    return {
      success: false,
      error: error.message || 'Swap failed'
    };
  }
};

/**
 * Buy tokens with SOL
 * @param {Object} wallet - Wallet adapter
 * @param {string} tokenMint - Token to buy
 * @param {number} solAmount - Amount of SOL to spend
 * @param {number} slippageBps - Slippage in basis points
 * @param {Function} onStatusUpdate - Status callback
 */
export const buyToken = async (wallet, tokenMint, solAmount, slippageBps = 100, onStatusUpdate = () => {}) => {
  const lamports = Math.floor(solAmount * 1e9); // Convert SOL to lamports
  return executeSwap(wallet, SOL_MINT, tokenMint, lamports, slippageBps, onStatusUpdate);
};

/**
 * Sell tokens for SOL
 * @param {Object} wallet - Wallet adapter
 * @param {string} tokenMint - Token to sell
 * @param {number} tokenAmount - Amount of tokens to sell (in smallest unit)
 * @param {number} slippageBps - Slippage in basis points
 * @param {Function} onStatusUpdate - Status callback
 */
export const sellToken = async (wallet, tokenMint, tokenAmount, slippageBps = 100, onStatusUpdate = () => {}) => {
  return executeSwap(wallet, tokenMint, SOL_MINT, tokenAmount, slippageBps, onStatusUpdate);
};

/**
 * Get token price in SOL
 * @param {string} tokenMint - Token mint address
 * @param {number} amount - Amount to check (default 1e9 = 1 token with 9 decimals)
 */
export const getTokenPrice = async (tokenMint, amount = 1e9) => {
  try {
    const quote = await getQuote(tokenMint, SOL_MINT, amount, 100);
    
    if (!quote.success) {
      return null;
    }
    
    // Price in SOL per token
    const priceInSol = quote.outAmount / 1e9 / (amount / 1e9);
    
    return {
      priceInSol,
      priceImpact: quote.priceImpact
    };
    
  } catch (error) {
    console.error('Error getting token price:', error);
    return null;
  }
};

export default {
  getQuote,
  buildSwapTransaction,
  executeSwap,
  buyToken,
  sellToken,
  getTokenPrice,
  SOL_MINT,
  USDC_MINT
};
